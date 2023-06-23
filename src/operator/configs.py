# configs.py
NAMESPACE = 'default'
API_GROUP = 'mygroup.mydomain'
API_VERSION = 'v1'
RESOURCE_KIND = 'spoks'

POD_NAME_MASTER = 'pgset-master-0'
POD_NAME_REPLICA_PREFIX = 'pgset-replica-'
POD_LABELS = {'app': 'postgres'}

STS_NAME_REPLICA = 'pgset-replica'
STS_PATH_MASTER = '../statefulset/pg-sts-master.yaml'
STS_PATH_REPLICA = '../statefulset/pg-sts-replica.yaml'

SVC_HEADLESS_POSTFIX = 'pgsql-headless.default.svc.cluster.local'

PGPOOL_LABELS = {'app': 'pgpool'}
PG_USERNAME = 'postgres'

MONITOR_INTERVAL = 300
MONITOR_IDLE = 60

URL_PROMETHEUS_SERVER_IN_CLUSTER = 'http://prometheus-server.default.svc.cluster.local:80/api/v1/query'