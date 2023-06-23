import datetime
import json
import subprocess
from operator_context import CustomContext
import pykube
import requests
import openai_client

from prometheus_api_client import PrometheusConnect
from prometheus_api_client.utils import parse_datetime

def get_prometheus_metrics2(logger):
    try:
        api = pykube.HTTPClient(pykube.KubeConfig.from_file())
        nodes = list(pykube.Node.objects(api).filter())
        node_ip = nodes[0].obj['status']['addresses'][0]['address']
        logger.info(f'call get_prometheus_metrics.............{node_ip}')

        url = f"http://{node_ip}:30090/api/v1/query"
        query = 'sum(container_memory_usage_bytes{namespace="default", container="postgres"}) / sum(container_spec_memory_limit_bytes{namespace="default", container="postgres"})'
        response = requests.get(url, params={'query': query})
        
        results = response.json()
        if results['status'] == 'success':
            logger.info('call success')
            metrics = results['data']['result']
            logger.info(json.dumps(metrics, indent=4))
            #openai_client.get_ai_advice(logger, metrics)
            return metrics
        else:
            logger.info('Failed to query Prometheus: ignoring metric collection.')
    except Exception as e:
        logger.info(f'Error accessing Prometheus or processing results: {e}. Ignoring metric collection.')


def get_prometheus_metrics(logger, memo: CustomContext):
    try:
        api = pykube.HTTPClient(pykube.KubeConfig.from_file())
        nodes = list(pykube.Node.objects(api).filter())
        node_ip = nodes[0].obj['status']['addresses'][0]['address']
        logger.info(f'call get_prometheus_metrics.............{node_ip}')

        url = f"http://{node_ip}:30090/api/v1/query"

        queries = {
            "node_cpu_utilization_percentage": 'avg (rate(node_cpu_seconds_total{mode!="idle"}[5m])) * 100',
            "node_memory_utilization_percentage": 'avg((node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100)',
            "postgres_pod_cpu_usage_seconds_total": 'sum(rate(container_cpu_usage_seconds_total{namespace="default", container="postgres"}[5m]))',
            "postgres_pod_memory_usage_percentage": 'sum(container_memory_usage_bytes{namespace="default", container="postgres"} / container_spec_memory_limit_bytes{namespace="default", container="postgres"}) * 100'
        }

        results = {}
        for key, query in queries.items():
            response = requests.get(url, params={'query': query})
            
            if response.status_code == 200:
                result = response.json()['data']['result']

                # Convert timestamp and calculate averages if necessary
                for res in result:
                    timestamp = float(res['value'][0])
                    dt_object = datetime.datetime.fromtimestamp(timestamp)
                    formatted_time = dt_object.strftime('%Y%m%d%H%M%S')
                    res['value'][0] = formatted_time

                results[key] = result
            else:
                logger.info(f'Query failed: {query}')
                results[key] = None

        results["current_standby_replicas"] = memo.current_standby_replicas
        #results["postgres_pod_memory_usage_percentage"] = 99
        metrics = json.dumps(results, indent=4)
        logger.info(metrics)
        
        prompt = """
                    Please analyze the load information provided and decide how to scale the PostgreSQL cluster, 
                    considering whether to scale in or scale out. 
                    Remember that the PostgreSQL cluster must have a minimum of 1 master and 1 replica, and a maximum of 3 replicas. 
                    Then, complete the JSON below accordingly:
                    ```json
                    {
                        "description": "<A brief description of the current load situation and the recommended scaling decision>",
                        "desired_standby_replicas": "<The target number of replicas for the PostgreSQL cluster>",
                        "alarm": "<A warning message if the scaling decision exceeds the cluster's capabilities>"
                    }
                    ```

                    Please return only the filled JSON, nothing more.
                """

        openai_client.get_ai_advice(logger, metrics + prompt)

    except Exception as e:
        logger.info(f'Error accessing Prometheus or processing results: {e}. Ignoring metric collection.')