#!/bin/bash
#name: init-backup
if [ -f /var/lib/postgresql/data/pgdata/standby.signal ]; then
    rm -rf /var/lib/postgresql/data/pgdata
    mkdir /var/lib/postgresql/data/pgdata
    PGPASSWORD=SuperSecret pg_basebackup -h pgset-master-0.pgsql-headless.default.svc.cluster.local -U replicarole -p 5432 -D /var/lib/postgresql/data/pgdata -Fp -Xs -P -R -S pgset1_slot
fi