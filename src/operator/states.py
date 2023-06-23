import dataclasses
from kubernetes import client, config #pip install kubernetes
from configs import *

@dataclasses.dataclass
class ReplicaState:
    has_been_restarted_by_opt: bool
    is_now_deleted_by_opt: bool

@dataclasses.dataclass()
class CustomContext:
    replica_state_dict: dict[str, ReplicaState]
    current_standby_replicas: None
    def __copy__(self) -> "CustomContext":
        return self

def list_spok_instances() -> dict:
    config.load_kube_config()
    api_instance = client.CustomObjectsApi()
    spoks = api_instance.list_namespaced_custom_object(
        group=API_GROUP, 
        version=API_VERSION, 
        namespace=NAMESPACE, 
        plural=RESOURCE_KIND)
    return spoks

def update_spok_instance(name: str, new_replicas: int):
    config.load_kube_config()

    api_instance = client.CustomObjectsApi()

    spok_instance = api_instance.get_namespaced_custom_object(
        group=API_GROUP,
        version=API_VERSION,
        namespace=NAMESPACE,
        plural=RESOURCE_KIND,
        name=name)

    spok_instance['spec']['standbyReplicas'] = new_replicas

    api_instance.patch_namespaced_custom_object(
        group=API_GROUP,
        version=API_VERSION,
        namespace=NAMESPACE,
        plural=RESOURCE_KIND,
        name=name,
        body=spok_instance)