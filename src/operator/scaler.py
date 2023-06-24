import subprocess
import time
import pykube
from states import ReplicaState
from configs import *

def add_pgpool_replicas(api, old_replicas, new_replicas, logger):
    configmap = pykube.ConfigMap.objects(api).get(name='pgpool-config')

    for i in range(old_replicas, new_replicas):
        id = i + 1
        backend_hostname = f"backend_hostname{id} = '{POD_NAME_REPLICA_PREFIX}{id}.{SVC_HEADLESS_POSTFIX}'"
        backend_port = f"backend_port{id} = 5432"
        backend_weight = f"backend_weight{id} = 1"
        backend_flag = f"backend_flag{id} = 'DISALLOW_TO_FAILOVER'"

        configmap.obj['data']['pgpool.conf'] += f"\n{backend_hostname}\n{backend_port}\n{backend_weight}\n{backend_flag}"

    configmap.update()
    logger.info(f"SPOK_LOG Added {new_replicas - old_replicas} replicas to pgpool ConfigMap")

def del_pgpool_replicas(api, old_replicas, new_replicas, logger):
    configmap = pykube.ConfigMap.objects(api).get(name='pgpool-config')

    for i in range(old_replicas, new_replicas, -1):
        lines = configmap.obj['data']['pgpool.conf'].split('\n')
        lines = [line for line in lines if not line.startswith(f"backend_hostname{i}") and not line.startswith(f"backend_port{i}") and not line.startswith(f"backend_weight{i}") and not line.startswith(f"backend_flag{i}")]
        configmap.obj['data']['pgpool.conf'] = '\n'.join(lines)

    configmap.update()
    logger.info(f"SPOK_LOG Removed {old_replicas - new_replicas} replicas from pgpool ConfigMap")

def scale_out(api, sts, old_replicas, new_replicas, logger, memo):
    logger.info(f"SPOK_LOG scale_out {old_replicas} to {new_replicas}\n{memo}")
    if new_replicas > old_replicas:
        add_pgpool_replicas(api, old_replicas, new_replicas, logger)
        for i in range(old_replicas, new_replicas):
            slot_name = f"pgset{i}_slot"
            command = [
                'kubectl', 'exec', '-it', POD_NAME_MASTER, '--',
                'psql', '-U', PG_USERNAME, '-c', 
                f"SELECT * FROM pg_create_physical_replication_slot('{slot_name}');"
            ]
            logger.info(f"SPOK_LOG scale_out is executing command: {command}")
            subprocess.run(command, check=True)
            time.sleep(1)
            logger.info(f"SPOK_LOG scale_out Created replication slot {slot_name} in the master database")

            pod_name = f"{POD_NAME_REPLICA_PREFIX}{i}"
            memo.current_standby_replicas = memo.current_standby_replicas + 1
            memo.replica_state_dict[pod_name] = ReplicaState(has_been_restarted_by_opt=False, is_now_deleted_by_opt=False)

        # The sts object has been modified by someone else, retry with the latest object
        sts.reload()
        sts.obj['spec']['replicas'] = new_replicas
        sts.update()
        logger.info(f"SPOK_LOG scale_out Updated replicas of pgset-replica StatefulSet to {new_replicas}")

def scale_in(api, sts, old_replicas, new_replicas, logger, memo):
    logger.info(f"SPOK_LOG scale_in {old_replicas} to {new_replicas}\n{memo}")
    if new_replicas < old_replicas:
        del_pgpool_replicas(api, old_replicas, new_replicas, logger)
        # The sts object has been modified by someone else, retry with the latest object
        sts.reload()
        sts.obj['spec']['replicas'] = new_replicas
        sts.update()
        logger.info(f"SPOK_LOG scale_in Updated replicas of pgset-replica StatefulSet to {new_replicas}")

        for i in range(old_replicas-1, new_replicas-1, -1):
            slot_name = f"pgset{i}_slot"
            logger.info(f"SPOK_LOG scale_in deleting slot {i}, {slot_name}")
            command = [
                'kubectl', 'exec', '-it', POD_NAME_MASTER, '--',
                'psql', '-U', PG_USERNAME, '-c', 
                f"SELECT pg_drop_replication_slot('{slot_name}');"
            ]
            logger.info(f"SPOK_LOG scale_in is executing command: {command}")
            subprocess.run(command, check=True)
            time.sleep(1)
            logger.info(f"SPOK_LOG scale_in Dropped replication slot {slot_name} in the master database")

            pod_name = f"{POD_NAME_REPLICA_PREFIX}{i}"
            memo.current_standby_replicas = memo.current_standby_replicas - 1
            del memo.replica_state_dict[pod_name]
            logger.info(f"SPOK_LOG scale_in Deleted state of pod {pod_name} from memo")

        
    