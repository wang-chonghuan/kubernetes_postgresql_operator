import asyncio
import dataclasses
import kopf
import pykube
import yaml

@dataclasses.dataclass()
class CustomContext:
    replica_restarted: bool
    def __copy__(self) -> "CustomContext":
        return self

# 创建集群
@kopf.on.create('mygroup.mydomain', 'v1', 'spoks')
def create_fn(body, spec, meta, namespace, logger,  memo: CustomContext, **kwargs):
    api = pykube.HTTPClient(pykube.KubeConfig.from_file())

    file_list = [
        '../storage/pv-0.yaml', 
        '../storage/pv-1.yaml', 
        '../service/headless-service.yaml', 
        '../statefulset/pg-sts-master.yaml', 
        '../statefulset/pg-sts-replica.yaml'
    ]
    memo.replica_restarted = False
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

    logger.info(f"Cluster created, memo.replica_restarted {memo.replica_restarted}")

# 当父资源被删除时，子资源将被自动删除，无需编写特定的删除函数
# 删除集群
@kopf.on.delete('mygroup.mydomain', 'v1', 'spoks')
def delete_fn(body, spec, meta, namespace, logger, memo: CustomContext, **kwargs):
    logger.info('Cluster deleted, and set replica_restarted to false')

@kopf.on.event('v1', 'pods', labels={'app': 'postgres'})
def pod_event_fn(event, body, logger, memo: CustomContext, **kwargs):

    logger.info(f"name:{body['metadata']['name']},phase:{body['status']['phase']},memo:{memo.replica_restarted}")
    api = pykube.HTTPClient(pykube.KubeConfig.from_file())

    if (body['metadata']['name'] == 'pgset-replica-0'  
        and body['status']['phase'] == 'Running'
        and memo.replica_restarted == False):
        logger.info('restarting replica')
        memo.replica_restarted = True
        pod_name = 'pgset-replica-0'
        pod = pykube.Pod.objects(api).get_by_name(pod_name)
        pod.delete()
        logger.info(f"Pod {pod_name} has been restarted.{memo.replica_restarted}")

if __name__ == '__main__':
    print('start operator main')
    kopf.configure(verbose=True)
    asyncio.run(kopf.operator(
        memo=CustomContext(replica_restarted = False)
    ))
