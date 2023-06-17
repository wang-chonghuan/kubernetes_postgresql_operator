#spok_opt.py
import asyncio
import dataclasses
import kopf
import pykube
import yaml
import subprocess
import time

@dataclasses.dataclass
class ReplicaState:
    has_been_restarted_by_opt: bool
    is_now_deleted_by_opt: bool

@dataclasses.dataclass()
class CustomContext:
    replica_state_dict: dict[str, ReplicaState]
    def __copy__(self) -> "CustomContext":
        return self

# 创建集群
@kopf.on.create('mygroup.mydomain', 'v1', 'spoks')
def create_fn(body, spec, meta, namespace, logger,  memo: CustomContext, **kwargs):
    api = pykube.HTTPClient(pykube.KubeConfig.from_file())

    file_list = [
        '../service/headless-service.yaml', 
        '../statefulset/pg-sts-master.yaml'
    ]
    # Initialize replica_state_dict
    memo.replica_state_dict = {"pgset-replica-0": ReplicaState(has_been_restarted_by_opt=False, is_now_deleted_by_opt=False)}
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

    # Wait for 5 seconds
    logger.info("Waiting for 5 seconds before starting pg-sts-replica...")
    time.sleep(5)

    # Create pg-sts-replica
    with open('../statefulset/pg-sts-replica.yaml', 'r') as file:
        resource_dict = yaml.safe_load(file)
        kopf.adopt(resource_dict)
        pykube.StatefulSet(api, resource_dict).create()

    logger.info(f"Cluster created, memo.replica_state_dict {memo.replica_state_dict}")


# 当父资源被删除时，子资源将被自动删除，无需编写特定的删除函数
# 删除集群
@kopf.on.delete('mygroup.mydomain', 'v1', 'spoks')
def delete_fn(body, spec, meta, namespace, logger, memo: CustomContext, **kwargs):
    memo.replica_state_dict = {} #必须重置，因为opt会在cr删除后持续运行，要保证下一个cr也能正常运行
    logger.info('Cluster deleted, and set replica_state_dict to {}')

@kopf.on.event('v1', 'pods', labels={'app': 'postgres'})
def pod_event_fn(event, body, logger, memo: CustomContext, **kwargs):

    logger.info(f"name:{body['metadata']['name']},\
                phase:{body['status']['phase']},\
                memo:{memo.replica_state_dict}")
    
    api = pykube.HTTPClient(pykube.KubeConfig.from_file())

    pod_name = body['metadata']['name']

    #如果该replica刚进入running状态，又显示是被Opt删除的，那么就恢复该状态为：不是被opt删除的，因为该事件已过
    #此处不该加上面一行的逻辑，原因在下面一行
    #发现了这个问题，当已经完成重启，进入了running状态，那边delete事件才收到，所以它以为不是opt重启的，就导致循环重启

    #如果该replica刚进入running状态，又没有被opt重启过，那么它需要被重启一次
    if (pod_name.startswith('pgset-replica-')  
        and body['status']['phase'] == 'Running'
        and memo.replica_state_dict.get(pod_name).has_been_restarted_by_opt == False):
        logger.info(f"restart replica once by config requred: {pod_name}")
        memo.replica_state_dict[pod_name] = ReplicaState(has_been_restarted_by_opt=True, is_now_deleted_by_opt=True)
        pod = pykube.Pod.objects(api).get_by_name(pod_name)
        pod.delete()
        logger.info(f"Pod {pod_name}开始重启，这是现在的状态{memo.replica_state_dict}")

@kopf.on.event('v1', 'pods', labels={'app': 'postgres'})
def pod_event_fn(event, body, logger, memo: CustomContext, **kwargs):

    # Log the entire body for debugging purposes
    logger.info(f"Received an event: {event['type']} for pod: {body['metadata']['name']}")

    pod_name = body['metadata']['name']
    #只处理从库节点的DELETED和CrashLoopBackOff
    if not pod_name.startswith('pgset-replica-'):
        return
    will_pod_restart = False

    # 检查是否是DELETED事件
    if event['type'] == 'DELETED':
        logger.info(f"Pod {body['metadata']['name']} has been deleted.")
        # Perform your logic here when a pod is deleted
        will_pod_restart = True

    # 检查是否是CrashLoopBackOff事件
    if event['type'] == 'MODIFIED':
        # Check if the pod is in 'CrashLoopBackOff' state
        for status in body.get('status', {}).get('containerStatuses', []):
            if status.get('state', {}).get('waiting', {}).get('reason') == 'CrashLoopBackOff':
                logger.info(f"Pod {body['metadata']['name']} has crashed.")
                # Perform your logic here when a pod crashes
                will_pod_restart = True
                break
    
    # 如果仅仅是状态MODIFIED了，但没有CrashLoopBackOff，说明只是普通的状态跳转，则不改动重启标识
    if not will_pod_restart:
        return
    logger.info(f"Pod {pod_name}遇到了删除事件，这是现在的状态{memo.replica_state_dict}")

    if memo.replica_state_dict == {}:
        logger.info(f"Pod {pod_name}遇到了删除事件，该删除事件是删除集群导致的，不变更状态")
        return

    #如果该pod失败，又是opt导致的，那么就忽略
    if will_pod_restart and memo.replica_state_dict.get(pod_name).is_now_deleted_by_opt == True:
        logger.info(f"该pod失败，又是opt导致的，那么说明处理过删除事件了，可以把is_now_deleted_by_opt恢复成false了")
        has_been_restarted_by_opt = memo.replica_state_dict.get(pod_name).has_been_restarted_by_opt
        memo.replica_state_dict[pod_name] = ReplicaState(has_been_restarted_by_opt, is_now_deleted_by_opt=False)
        logger.info(f"Pod {pod_name}已收到opt删除事件，不用再处理该事件了，这是现在的状态{memo.replica_state_dict}")

    #如果该pod失败，但不是opt导致的，那么要重置该副本的状态
    elif will_pod_restart and memo.replica_state_dict.get(pod_name).is_now_deleted_by_opt == False:
        logger.info(f"该pod失败，但不是opt导致的，那么要重置该副本的状态")
        memo.replica_state_dict[pod_name] = ReplicaState(has_been_restarted_by_opt=False, is_now_deleted_by_opt=False)
        

@kopf.on.update('mygroup.mydomain', 'v1', 'spoks')
def update_replicas_fn(spec, status, namespace, logger, memo: CustomContext, **kwargs):
    # 获取旧的和新的副本数量
    old_replicas = status.get('standbyReplicas', 1)
    new_replicas = spec.get('standbyReplicas', 1)
    logger.info(f"++++++++++++++++Updating standbyReplicas from {old_replicas} to {new_replicas}")

    # 获取Kubernetes API客户端
    api = pykube.HTTPClient(pykube.KubeConfig.from_file())
    
    # 获取StatefulSet对象
    sts = pykube.StatefulSet.objects(api).filter(namespace=namespace).get(name='pgset-replica')

    # 如果新的副本数量比旧的多，那么为新的副本创建复制插槽，同时在opt中备案
    if new_replicas > old_replicas:
        for i in range(old_replicas, new_replicas):
            slot_name = f"pgset{i}_slot"
            # 指定命令
            command = [
                'kubectl', 'exec', '-it', 'pgset-master-0', '--',
                'psql', '-U', 'postgres', '-c', 
                f"SELECT * FROM pg_create_physical_replication_slot('{slot_name}');"
            ]
            # 运行命令
            subprocess.run(command, check=True)
            logger.info(f"Created replication slot {slot_name} in the master database")
            #新创建的replica要在memo里备案，设定其应该被重启一次
            pod_name = f"pgset-replica-{i}"
            memo.replica_state_dict[pod_name] = ReplicaState(has_been_restarted_by_opt=False, is_now_deleted_by_opt=False)


    # 更新StatefulSet的副本数量
    sts.obj['spec']['replicas'] = new_replicas
    sts.update()

    logger.info(f"================Updated replicas of pgset-replica StatefulSet to {new_replicas}")


if __name__ == '__main__':
    print('start operator main with state replica_state_dict')
    kopf.configure(verbose=True)
    asyncio.run(kopf.operator(
        memo=CustomContext(replica_state_dict = {})
    ))

