#!/bin/bash
set -e
# Poll until Postgres is ready
until pg_isready -U postgres; do
    echo "Waiting for PostgreSQL to start..."
    sleep 2
done
echo "Post-start setup as Replica..."
# Perform replica specific setup
touch /var/lib/postgresql/data/pgdata/standby.signal
echo "primary_conninfo = 'user=replicarole password=SuperSecret host=pgset-master-0.pgsql-headless.default.svc.cluster.local port=5432 sslmode=prefer sslcompression=0 gssencmode=prefer krbsrvname=postgres target_session_attrs=any'" >> /var/lib/postgresql/data/pgdata/postgresql.auto.conf
echo "primary_slot_name = 'pgset1_slot'" >> /var/lib/postgresql/data/pgdata/postgresql.auto.conf
# Update max_wal_senders
sed -i "s/^#*max_wal_senders =.*$/max_wal_senders = 10/" /var/lib/postgresql/data/pgdata/postgresql.conf
psql -U postgres -c "SELECT pg_reload_conf();"