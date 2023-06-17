#spok_opt.py
import asyncio
import dataclasses
import kopf
import pykube
import yaml
import subprocess

@dataclasses.dataclass()
class CustomContext:
    replicas_restarted: dict
    def __copy__(self) -> "CustomContext":
        return self

import time

# 创建集群
@kopf.on.create('mygroup.mydomain', 'v1', 'spoks')
def create_fn(body, spec, meta, namespace, logger,  memo: CustomContext, **kwargs):
    api = pykube.HTTPClient(pykube.KubeConfig.from_file())

    file_list = [
        '../service/headless-service.yaml', 
        '../statefulset/pg-sts-master.yaml'
    ]
    # Initialize replicas_restarted
    memo.replicas_restarted = {"pgset-replica-0": False}
    logger.info(f"Cluster created, memo.replicas_restarted {memo.replicas_restarted}")
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

    logger.info(f"Cluster created, memo.replicas_restarted {memo.replicas_restarted}")


# 当父资源被删除时，子资源将被自动删除，无需编写特定的删除函数
# 删除集群
@kopf.on.delete('mygroup.mydomain', 'v1', 'spoks')
def delete_fn(body, spec, meta, namespace, logger, memo: CustomContext, **kwargs):
    logger.info('Cluster deleted, and set replicas_restarted to false')

@kopf.on.event('v1', 'pods', labels={'app': 'postgres'})
def pod_event_fn(event, body, logger, memo: CustomContext, **kwargs):

    logger.info(f"name:{body['metadata']['name']},phase:{body['status']['phase']},memo:{memo.replicas_restarted}")
    api = pykube.HTTPClient(pykube.KubeConfig.from_file())

    pod_name = body['metadata']['name']
    if (pod_name.startswith('pgset-replica-')  
        and body['status']['phase'] == 'Running'
        and memo.replicas_restarted.get(pod_name, False) == False):
        logger.info(f"Restarting {pod_name}")
        memo.replicas_restarted[pod_name] = True
        pod = pykube.Pod.objects(api).get_by_name(pod_name)
        pod.delete()
        logger.info(f"Pod {pod_name} has been restarted.{memo.replicas_restarted[pod_name]}")


@kopf.on.update('mygroup.mydomain', 'v1', 'spoks')
def update_replicas_fn(spec, status, namespace, logger, **kwargs):
    # 获取旧的和新的副本数量
    old_replicas = status.get('standbyReplicas', 1)
    new_replicas = spec.get('standbyReplicas', 1)
    logger.info(f"++++++++++++++++Updating standbyReplicas from {old_replicas} to {new_replicas}")

    # 获取Kubernetes API客户端
    api = pykube.HTTPClient(pykube.KubeConfig.from_file())
    
    # 获取StatefulSet对象
    sts = pykube.StatefulSet.objects(api).filter(namespace=namespace).get(name='pgset-replica')

    # 如果新的副本数量比旧的多，那么为新的副本创建复制插槽
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

    # 更新StatefulSet的副本数量
    sts.obj['spec']['replicas'] = new_replicas
    sts.update()

    logger.info(f"================Updated replicas of pgset-replica StatefulSet to {new_replicas}")


if __name__ == '__main__':
    print('start operator main')
    kopf.configure(verbose=True)
    asyncio.run(kopf.operator(
        memo=CustomContext(replicas_restarted = {})
    ))

