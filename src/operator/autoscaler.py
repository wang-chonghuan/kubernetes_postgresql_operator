import subprocess
import pgpool_update
from operator_context import ReplicaState

def scale_out(api, sts, old_replicas, new_replicas, logger, memo):
    if new_replicas > old_replicas:
        pgpool_update.add_pgpool_replicas(api, old_replicas, new_replicas, logger)
        for i in range(old_replicas, new_replicas):
            slot_name = f"pgset{i}_slot"
            command = [
                'kubectl', 'exec', '-it', 'pgset-master-0', '--',
                'psql', '-U', 'postgres', '-c', 
                f"SELECT * FROM pg_create_physical_replication_slot('{slot_name}');"
            ]
            subprocess.run(command, check=True)
            logger.info(f"Created replication slot {slot_name} in the master database")

            pod_name = f"pgset-replica-{i}"
            memo.current_standby_replicas = memo.current_standby_replicas + 1
            memo.replica_state_dict[pod_name] = ReplicaState(has_been_restarted_by_opt=False, is_now_deleted_by_opt=False)

        # The sts object has been modified by someone else, retry with the latest object
        sts.reload()
        sts.obj['spec']['replicas'] = new_replicas
        sts.update()
        logger.info(f"Updated replicas of pgset-replica StatefulSet to {new_replicas}")

def scale_in(api, sts, old_replicas, new_replicas, logger, memo):
    if new_replicas < old_replicas:
        pgpool_update.del_pgpool_replicas(api, old_replicas, new_replicas, logger)
        # The sts object has been modified by someone else, retry with the latest object
        sts.reload()
        sts.obj['spec']['replicas'] = new_replicas
        sts.update()
        logger.info(f"Updated replicas of pgset-replica StatefulSet to {new_replicas}")

        for i in range(old_replicas-1, new_replicas-1, -1):
            slot_name = f"pgset{i}_slot"
            command = [
                'kubectl', 'exec', '-it', 'pgset-master-0', '--',
                'psql', '-U', 'postgres', '-c', 
                f"SELECT pg_drop_replication_slot('{slot_name}');"
            ]
            subprocess.run(command, check=True)
            logger.info(f"Dropped replication slot {slot_name} in the master database")

            pod_name = f"pgset-replica-{i}"
            memo.current_standby_replicas = memo.current_standby_replicas - 1
            del memo.replica_state_dict[pod_name]
            logger.info(f"Deleted state of pod {pod_name} from memo")