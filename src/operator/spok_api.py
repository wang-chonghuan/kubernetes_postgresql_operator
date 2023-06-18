from kubernetes import client, config #pip install kubernetes

def get_spok_instance(name: str, namespace: str = 'default'):
    # 加载kubeconfig
    config.load_kube_config()

    # 创建一个CustomObjectsApi实例
    api_instance = client.CustomObjectsApi()

    # 指定API组，版本和命名空间
    group = 'mygroup.mydomain'  # 修改为你的组名
    version = 'v1'
    plural = 'spoks'  # 通常是CRD种类的复数形式

    try:
        # 获取特定的spok实例
        spok_instance = api_instance.get_namespaced_custom_object(group, version, namespace, plural, name)
        return spok_instance
    except client.rest.ApiException as e:
        print(f"Exception when calling CustomObjectsApi->get_namespaced_custom_object: {e}")

def list_spok_instances(namespace: str = "default") -> dict:
    config.load_kube_config()
    api_instance = client.CustomObjectsApi()
    group = 'mygroup.mydomain'  
    version = 'v1'
    plural = 'spoks'
    spoks = api_instance.list_namespaced_custom_object(
        group=group, 
        version=version, 
        namespace=namespace, 
        plural=plural)
    return spoks

def update_spok_instance(name: str, namespace: str, new_replicas: int):
    # 配置kubeconfig
    config.load_kube_config()

    # 创建一个客户端实例
    api_instance = client.CustomObjectsApi()

    # 定义CRD的组，版本和资源(plural)名称
    group = 'mygroup.mydomain'  # CRD的group
    version = 'v1'  # CRD的版本
    plural = 'spoks'  # CRD的plural

    # 获取当前的Spok实例
    spok_instance = api_instance.get_namespaced_custom_object(
        group=group,
        version=version,
        namespace=namespace,
        plural=plural,
        name=name)

    # 修改副本数
    spok_instance['spec']['standbyReplicas'] = new_replicas
    
    # 更新Spok实例
    api_instance.patch_namespaced_custom_object(
        group=group,
        version=version,
        namespace=namespace,
        plural=plural,
        name=name,
        body=spok_instance)
