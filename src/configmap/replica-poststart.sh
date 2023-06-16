#!/bin/bash
set -e

# Check if the directory exists, if not, create it
if [ ! -d "/spok_logs" ]; then
  mkdir -p /spok_logs
fi

LOG_PATH="/spok_logs/poststart.log"
echo "ENV values: ${SYNC_COMMIT}, ${POD_NAME}" >> ${LOG_PATH}

# Poll until Postgres is ready
until pg_isready -U postgres; do
    echo "Waiting for PostgreSQL to start..." >> ${LOG_PATH}
    sleep 2
done
echo "Post-start setup as Replica..." >> ${LOG_PATH}

# Perform replica specific setup
touch /var/lib/postgresql/data/pgdata/standby.signal

# Build the primary_conninfo string
PRIMARY_CONNINFO="user=replicarole password=SuperSecret host=pgset-master-0.pgsql-headless.default.svc.cluster.local port=5432 sslmode=prefer sslcompression=0 gssencmode=prefer krbsrvname=postgres target_session_attrs=any"

# Check if SYNC_COMMIT is true and append application_name if necessary
if [ "${SYNC_COMMIT}" = "true" ]; then
    PRIMARY_CONNINFO+=" application_name=${POD_NAME}.pgsql-headless.default.svc.cluster.local"
    echo "SYNC_COMMIT is true, appended application_name" >> ${LOG_PATH}
fi

# Write primary_conninfo to the configuration
echo "primary_conninfo = '${PRIMARY_CONNINFO}'" >> /var/lib/postgresql/data/pgdata/postgresql.auto.conf

# Get the last part of the POD_NAME (the replica number)
REPLICA_NUMBER=${POD_NAME##*-}
echo "REPLICA_NUMBER: ${REPLICA_NUMBER}" >> ${LOG_PATH}
echo "primary_slot_name = 'pgset${REPLICA_NUMBER}_slot'" >> /var/lib/postgresql/data/pgdata/postgresql.auto.conf
# Update max_wal_senders
sed -i "s/^#*max_wal_senders =.*$/max_wal_senders = 10/" /var/lib/postgresql/data/pgdata/postgresql.conf
psql -U postgres -c "SELECT pg_reload_conf();"
