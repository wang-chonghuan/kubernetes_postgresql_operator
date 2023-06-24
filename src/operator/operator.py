#spok_opt.py
import asyncio
import time
from typing import Optional
import kopf
import pykube
import yaml
import monitor as prom_gpt_scaler
import states
from states import CustomContext
from states import ReplicaState
import scaler
from configs import *

#?! multiple spok-cluster instances
@kopf.on.startup()
def on_startup(logger, memo: Optional[CustomContext], **_):
    if memo is None:
        memo = CustomContext()
    
    spoks = states.list_spok_instances()
    
    for spok in spoks.get('items', []):
        name = spok['metadata']['name']
        memo.current_standby_replicas = spok['spec'].get('standbyReplicas')
        break # get the only spok and init memo by it

    api = pykube.HTTPClient(pykube.KubeConfig.from_file()) # Create an API client
    pods = pykube.Pod.objects(api).filter(namespace=NAMESPACE) # Fetch all pods in a particular namespace
    for pod in pods:
        pod_name = pod.obj['metadata']['name']
        pod_status = pod.obj.get('status', {}).get('phase', '')
        if pod_name.startswith(POD_NAME_REPLICA_PREFIX):
            # Add it to the replica_state_dict
            memo.replica_state_dict[pod_name] = ReplicaState(has_been_restarted_by_opt=False, is_now_deleted_by_opt=False)
    logger.info(f"SPOK_LOG Startup: Initialized memo.current_standby_replicas to {memo.current_standby_replicas}")


@kopf.on.create(API_GROUP, API_VERSION, RESOURCE_KIND)
def create_fn(spec, name, namespace, logger, memo: CustomContext, **kwargs):
    api = pykube.HTTPClient(pykube.KubeConfig.from_file())
    
    standbyReplicas = spec.get('standbyReplicas')

    # Ensure standbyReplicas is an integer between 1 and 3
    if not isinstance(standbyReplicas, int) or not 0 <= standbyReplicas <= 3:
        logger.error("SPOK_LOG_ standbyReplicas must be an integer between 0 and 3")
        return

    # Initialize replica_state_dict
    memo.replica_state_dict = {}
    memo.current_standby_replicas = 0

    file_list = [STS_PATH_MASTER]
    for file_name in file_list:
        with open(file_name, 'r') as file:
            resource_dict = yaml.safe_load(file)
            kopf.adopt(resource_dict)
            kind = resource_dict.get("kind")
            if kind == "PersistentVolume":
                pykube.PersistentVolume(api, resource_dict).create()
            elif kind == "Service":
                pykube.Service(api, resource_dict).create()
            elif kind == "StatefulSet":
                pykube.StatefulSet(api, resource_dict).create()

    # Polling for master ready
    logger.info("SPOK_LOG make sure master is in running state before starting pg-sts-replica...")
    # Start of modification - Block and check the status of the pod before proceeding
    pod_running = False
    while not pod_running:
        logger.info("SPOK_LOG Waiting for 3 seconds before checking pgset-master-0 status...")
        time.sleep(3)
        try:
            pod = pykube.Pod.objects(api).get_by_name(POD_NAME_MASTER)
            pod_status = pod.obj.get('status', {}).get('phase', '')
            if pod_status.lower() == "running":
                pod_running = True
                logger.info(f"SPOK_LOG {POD_NAME_MASTER} is now running.")
            else:
                logger.info(f"SPOK_LOG {POD_NAME_MASTER} is in status {pod_status}, waiting...")
        except pykube.exceptions.ObjectDoesNotExist:
            logger.info(f"SPOK_LOG {POD_NAME_MASTER} does not exist, waiting...")
    # End of modification
    
    #First create a sts with only 0 replica, then if there are more nodes, scale_out on it
    with open(STS_PATH_REPLICA, 'r') as file:
        resource_dict = yaml.safe_load(file)
        resource_dict['spec']['replicas'] = 0
        kopf.adopt(resource_dict)
        sts = pykube.StatefulSet(api, resource_dict)
        sts.create()

    # You can't use update_spok_instance here, because the number of copies in the spok spec is originally 2, you update 2, it won't cause a callback response
    logger.info(f"SPOK_LOG A total of {standbyReplicas} will be created. Start to scale out the remaining copies")
    if standbyReplicas > memo.current_standby_replicas:
        scaler.scale_out(api, sts, memo.current_standby_replicas, standbyReplicas, logger, memo)

    logger.info(f"SPOK_LOG Cluster created, memo.replica_state_dict {memo.replica_state_dict}")


# Deleting clusters. When the parent resource is deleted, the child resources will be deleted automatically
@kopf.on.delete(API_GROUP, API_VERSION, RESOURCE_KIND)
def delete_fn(body, spec, meta, namespace, logger, memo: CustomContext, **kwargs):
    # It must be reset, because the opt will continue to run after the cr is deleted, to ensure that the next cr will also run properly
    memo.replica_state_dict = {} 
    memo.current_standby_replicas = 0
    logger.info('SPOK_LOG Cluster deleted, and set replica_state_dict to {}')

@kopf.on.event(API_VERSION, 'pods', labels=POD_LABELS)
def pod_event_fn(event, body, logger, memo: CustomContext, **kwargs):

    logger.info(f"SPOK_LOG name:{body['metadata']['name']},\
                phase:{body['status']['phase']},\
                memo:{memo.replica_state_dict}")
    
    api = pykube.HTTPClient(pykube.KubeConfig.from_file())

    pod_name = body['metadata']['name']

    #如果该replica刚进入running状态，又显示是被Opt删除的，那么就恢复该状态为：不是被opt删除的，因为该事件已过
    #此处不该加上面一行的逻辑，原因在下面一行
    #发现了这个问题，当已经完成重启，进入了running状态，那边delete事件才收到，所以它以为不是opt重启的，就导致循环重启
    #如果该replica刚进入running状态，又没有被opt重启过，那么它需要被重启一次
    #If the replica has just entered the running state, and it shows that it was deleted by Opt, then restore the state to: not deleted by opt, because the event has passed
    #The logic in the previous line should not be added here, the reason is in the following line
    # found the problem, when the restart has been completed and entered the running state, the delete event was received, so it thought it was not the opt restart, resulting in a loop restart
    #If the replica just entered the running state and has not been restarted by the opt, then it needs to be restarted once
    replica_state = memo.replica_state_dict.get(pod_name)
    if (pod_name.startswith(POD_NAME_REPLICA_PREFIX)  
        and body['status']['phase'] == 'Running'
        and replica_state
        and replica_state.has_been_restarted_by_opt == False):
        logger.info(f"SPOK_LOG restart replica once by config requred: {pod_name}")
        memo.replica_state_dict[pod_name] = ReplicaState(has_been_restarted_by_opt=True, is_now_deleted_by_opt=True)
        pod = pykube.Pod.objects(api).get_by_name(pod_name)
        pod.delete()
        logger.info(f"SPOK_LOG Pod {pod_name}Start restart, this is the current state{memo.replica_state_dict}")

@kopf.on.event(API_VERSION, 'pods', labels=POD_LABELS)
def pod_event_fn(event, body, logger, memo: CustomContext, **kwargs):

    # Log the entire body for debugging purposes
    logger.info(f"SPOK_LOG Received an event: {event['type']} for pod: {body['metadata']['name']}")

    pod_name = body['metadata']['name']
    #Only handle DELETED and CrashLoopBackOff of slave nodes
    if not pod_name.startswith(POD_NAME_REPLICA_PREFIX):
        return
    will_pod_restart = False

    # Check if it is a DELETED event
    if event['type'] == 'DELETED':
        logger.info(f"SPOK_LOG Pod {body['metadata']['name']} has been deleted.")
        # Perform your logic here when a pod is deleted
        will_pod_restart = True

    # Check if it is a CrashLoopBackOff event
    if event['type'] == 'MODIFIED':
        # Check if the pod is in 'CrashLoopBackOff' state
        for status in body.get('status', {}).get('containerStatuses', []):
            if status.get('state', {}).get('waiting', {}).get('reason') == 'CrashLoopBackOff':
                logger.info(f"SPOK_LOG Pod {body['metadata']['name']} has crashed.")
                # Perform your logic here when a pod crashes
                will_pod_restart = True
                break
    
    # 如果仅仅是状态MODIFIED了，但没有CrashLoopBackOff，说明只是普通的状态跳转，则不改动重启标识
    # If only the state MODIFIED, but no CrashLoopBackOff, indicating that it is just an ordinary state jump, then do not change the restart logo
    if not will_pod_restart:
        return
    logger.info(f"SPOK_LOG Pod {pod_name} encountered a delete event and this is the current state {memo.replica_state_dict}")

    if memo.replica_state_dict == {}:
        logger.info(f"SPOK_LOG Pod {pod_name} encountered a delete event, which is caused by the deletion of a cluster and does not change state")
        return

    # 如果该pod失败，又是opt导致的，那么就忽略
    # If the pod fails and it is caused by the opt, then ignore
    if (will_pod_restart 
        and memo.replica_state_dict.get(pod_name) 
        and memo.replica_state_dict.get(pod_name).is_now_deleted_by_opt == True):
        
        logger.info(f"SPOK_LOG The pod fails and is caused by the opt, then it means that the deletion event has been processed, and you can restore is_now_deleted_by_opt to false")
        has_been_restarted_by_opt = memo.replica_state_dict.get(pod_name).has_been_restarted_by_opt
        memo.replica_state_dict[pod_name] = ReplicaState(has_been_restarted_by_opt, is_now_deleted_by_opt=False)
        logger.info(f"SPOK_LOG Pod {pod_name} has received the opt delete event and does not need to process it anymore, this is the current state {memo.replica_state_dict}")

    # 如果该pod失败，但不是opt导致的，那么要重置该副本的状态
    # If the pod fails, but not caused by the opt, then reset the state of the copy
    elif (will_pod_restart 
          and memo.replica_state_dict.get(pod_name) 
          and memo.replica_state_dict.get(pod_name).is_now_deleted_by_opt == False):
        
        logger.info(f"SPOK_LOG The pod failed, but not caused by the opt, then reset the state of the copy")
        memo.replica_state_dict[pod_name] = ReplicaState(has_been_restarted_by_opt=False, is_now_deleted_by_opt=False)


@kopf.on.update(API_GROUP, API_VERSION, RESOURCE_KIND)
def update_replicas_fn(spec, status, namespace, name, logger, memo: CustomContext, **kwargs):

    api = pykube.HTTPClient(pykube.KubeConfig.from_file())
    
    #not working: spok = pykube.Spok.objects(api).filter(namespace=namespace).get(name=name)
    #not working: spok = spok_api.get_spok_instance(name)
    old_replicas = memo.current_standby_replicas
    new_replicas = spec.get('standbyReplicas', 1)
    logger.info(f"SPOK_LOG Detect spok's standbyReplicas change and start auto-scaling, From {old_replicas} to {new_replicas}")

    if old_replicas != new_replicas:
        logger.info(f"SPOK_LOG Updating standbyReplicas from {old_replicas} to {new_replicas}")

        # 这里遇到的问题是修改cr导致scale_out以后，status里读到的standbyReplicas始终是 1，不会变成2。所以我想从2扩容到3时，就失败了。解决方法是要手动更新status里的这个值，否则它不会变。更新 Spok 对象
        #The problem I encountered here was that after changing cr to cause scale_out, the standbyReplicas read in status would always be 1 and would not change to 2. So when I tried to scale from 2 to 3, it failed. The solution is to update this value in status manually, otherwise it will not change. Update Spok object
        #states.update_spok_instance(name, new_replicas)

        sts = pykube.StatefulSet.objects(api).get(name=STS_NAME_REPLICA)

        scaler.scale_out(api, sts, old_replicas, new_replicas, logger, memo)
        scaler.scale_in(api, sts, old_replicas, new_replicas, logger, memo)

        pgpool_pod = pykube.Pod.objects(api).filter(selector=PGPOOL_LABELS).get()
        pgpool_pod.delete()

        return {'status': {'standbyReplicas': new_replicas}}  # Update kopf's status, not sure it works

@kopf.timer(API_GROUP, API_VERSION, RESOURCE_KIND, interval=MONITOR_INTERVAL, idle=MONITOR_IDLE)
def monitor(spec, logger, memo: CustomContext, name, namespace, **kwargs):
    logger.info(f"SPOK_LOG Spok is periodic monitoring prometheus metrics ....................................")
    api = pykube.HTTPClient(pykube.KubeConfig.from_file())
    sts = pykube.StatefulSet.objects(api).get(name=STS_NAME_REPLICA)
    prom_gpt_scaler.scale_on_metrics(api, logger, memo, name, namespace)

if __name__ == '__main__':
    print('SPOK_LOG start operator main with state replica_state_dict')
    kopf.configure(verbose=True)
    asyncio.run(kopf.operator(
        memo=CustomContext(replica_state_dict = {}, current_standby_replicas = 0)
    ))

