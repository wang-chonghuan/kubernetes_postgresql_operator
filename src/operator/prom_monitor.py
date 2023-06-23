import datetime
import json
import subprocess
import pykube
import requests
import openai_client

from prometheus_api_client import PrometheusConnect
from prometheus_api_client.utils import parse_datetime

def get_prometheus_metrics(logger):
    try:
        api = pykube.HTTPClient(pykube.KubeConfig.from_file())
        nodes = list(pykube.Node.objects(api).filter())
        node_ip = nodes[0].obj['status']['addresses'][0]['address']
        logger.info(f'call get_prometheus_metrics.............{node_ip}')

        url = f"http://{node_ip}:30090/api/v1/query"
        query = 'avg(1 - rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100'
        response = requests.get(url, params={'query': query})
        
        results = response.json()
        if results['status'] == 'success':
            logger.info('call success')
            metrics = results['data']['result']
            logger.info(json.dumps(metrics, indent=4))
            openai_client.get_ai_advice(logger, metrics)
            return metrics
        else:
            logger.info('Failed to query Prometheus: ignoring metric collection.')
    except Exception as e:
        logger.info(f'Error accessing Prometheus or processing results: {e}. Ignoring metric collection.')
