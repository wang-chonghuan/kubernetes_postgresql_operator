#!/bin/bash
set -e
# Check if the directory exists, if not, create it
if [ ! -d "/spok_logs" ]; then
  mkdir -p /spok_logs
fi
LOG_PATH="/spok_logs/poststart.log"
echo "SYNC_COMMIT value: ${SYNC_COMMIT}" >> ${LOG_PATH}

# Poll until Postgres is ready
until pg_isready -U postgres; do
    echo "Waiting for PostgreSQL to start..." >> ${LOG_PATH}
    sleep 2
done
echo "Post-start setup as Master..." >> ${LOG_PATH}

# Perform master specific setup
psql -U postgres -c "ALTER SYSTEM SET listen_addresses TO '*';"
psql -U postgres -c "ALTER SYSTEM SET wal_level TO replica;"
psql -U postgres -c "ALTER SYSTEM SET hot_standby TO on;"
psql -U postgres -c "SELECT pg_reload_conf();"
psql -U postgres -c "CREATE USER replicarole WITH REPLICATION ENCRYPTED PASSWORD 'SuperSecret';"
echo "host replication replicarole all md5" >> /var/lib/postgresql/data/pgdata/pg_hba.conf
sed -i "s/^#*max_wal_senders =.*$/max_wal_senders = 10/" /var/lib/postgresql/data/pgdata/postgresql.conf
psql -U postgres -c "SELECT pg_reload_conf();"
psql -U postgres -c "SELECT * FROM pg_create_physical_replication_slot('pgset1_slot');"

# Check if SYNC_COMMIT is true
if [ "${SYNC_COMMIT}" = "true" ]; then
    echo "Set sync configs" >> ${LOG_PATH}
    psql -U postgres -c "ALTER SYSTEM SET synchronous_standby_names TO '*';"
    psql -U postgres -c "ALTER SYSTEM SET synchronous_commit TO on;"
    psql -U postgres -c "SELECT pg_reload_conf();"
fi
