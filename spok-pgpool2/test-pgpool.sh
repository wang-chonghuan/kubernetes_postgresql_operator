#!/bin/bash

# 先获取pgpool-II的Pod名称
POD_NAME=$(kubectl get pods -l app=pgpool -o jsonpath="{.items[0].metadata.name}")

# 使用psql命令行工具进行查询
kubectl exec -it $POD_NAME -- psql -h localhost -p 9999 -U postgres
