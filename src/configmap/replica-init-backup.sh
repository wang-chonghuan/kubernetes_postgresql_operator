#!/bin/bash
#name: init-backup
# if the db is not installed, ignore.
# if the db has already been installed, clean the data and start to sync from master
if [ -f /var/lib/postgresql/data/pgdata/standby.signal ]; then
    rm -rf /var/lib/postgresql/data/pgdata
    mkdir /var/lib/postgresql/data/pgdata
    # Get the last part of the POD_NAME (the replica number)
    REPLICA_NUMBER=${POD_NAME##*-}
    # Print POD_NAME and REPLICA_NUMBER for debugging
    echo "POD_NAME is ${POD_NAME}"
    echo "REPLICA_NUMBER is ${REPLICA_NUMBER}"
    PGPASSWORD=SuperSecret pg_basebackup -h pgset-master-0.pgsql-headless.default.svc.cluster.local -U replicarole -p 5432 -D /var/lib/postgresql/data/pgdata -Fp -Xs -P -R -S pgset${REPLICA_NUMBER}_slot
fi
