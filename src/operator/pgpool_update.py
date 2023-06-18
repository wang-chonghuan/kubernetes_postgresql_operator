import pykube

def add_pgpool_replicas(api, old_replicas, new_replicas, logger):
    configmap = pykube.ConfigMap.objects(api).get(name='pgpool-config')

    for i in range(old_replicas, new_replicas):
        id = i + 1
        backend_hostname = f"backend_hostname{id} = 'pgset-replica-{id}.pgsql-headless.default.svc.cluster.local'"
        backend_port = f"backend_port{id} = 5432"
        backend_weight = f"backend_weight{id} = 1"
        backend_flag = f"backend_flag{id} = 'DISALLOW_TO_FAILOVER'"

        configmap.obj['data']['pgpool.conf'] += f"\n{backend_hostname}\n{backend_port}\n{backend_weight}\n{backend_flag}"

    configmap.update()
    logger.info(f"Added {new_replicas - old_replicas} replicas to pgpool ConfigMap")

def del_pgpool_replicas(api, old_replicas, new_replicas, logger):
    configmap = pykube.ConfigMap.objects(api).get(name='pgpool-config')

    for i in range(old_replicas, new_replicas, -1):
        lines = configmap.obj['data']['pgpool.conf'].split('\n')
        lines = [line for line in lines if not line.startswith(f"backend_hostname{i}") and not line.startswith(f"backend_port{i}") and not line.startswith(f"backend_weight{i}") and not line.startswith(f"backend_flag{i}")]
        configmap.obj['data']['pgpool.conf'] = '\n'.join(lines)

    configmap.update()
    logger.info(f"Removed {old_replicas - new_replicas} replicas from pgpool ConfigMap")