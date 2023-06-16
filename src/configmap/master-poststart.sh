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

# Check if the user already exists
user_exists=$(psql -U postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='replicarole'")
# If the user doesn't exist, create it
if [ "$user_exists" != "1" ]; then
    psql -U postgres -c "CREATE USER replicarole WITH REPLICATION ENCRYPTED PASSWORD 'SuperSecret';"
else
    echo "User replicarole already exists."
fi

if ! grep -qP "^\s*#.*host replication replicarole all md5" /var/lib/postgresql/data/pgdata/pg_hba.conf; then
  echo "host replication replicarole all md5" >> /var/lib/postgresql/data/pgdata/pg_hba.conf
fi
psql -U postgres -c "ALTER SYSTEM SET max_wal_senders = 10;"
psql -U postgres -c "SELECT pg_reload_conf();"

# Check if the replication slot already exists
slot_exists=$(psql -U postgres -tAc "SELECT 1 FROM pg_replication_slots WHERE slot_name='pgset1_slot'")
# If the slot doesn't exist, create it
if [ "$slot_exists" != "1" ]; then
    psql -U postgres -c "SELECT pg_create_physical_replication_slot('pgset1_slot');"
else
    echo "Replication slot pgset1_slot already exists."
fi

# Check if SYNC_COMMIT is true
if [ "${SYNC_COMMIT}" = "true" ]; then
    echo "Set sync configs" >> ${LOG_PATH}
    psql -U postgres -c "ALTER SYSTEM SET synchronous_standby_names TO '*';"
    psql -U postgres -c "ALTER SYSTEM SET synchronous_commit TO on;"
    psql -U postgres -c "SELECT pg_reload_conf();"
fi
