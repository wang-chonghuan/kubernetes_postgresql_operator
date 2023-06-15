#!/bin/bash

# 检查命令行参数是否存在
if [ $# -ne 1 ]; then
    echo "Usage: $0 <path_to_scripts>"
    exit 1
fi

# 获取脚本目录路径
SCRIPTS_DIR=$1

# 定义 ConfigMap 名称
CONFIGMAP_NAME="spok-sts-scripts"

# 删除旧的 ConfigMap，忽略不存在的 ConfigMap 错误
kubectl delete configmap ${CONFIGMAP_NAME} --ignore-not-found

# 检查目录是否存在 .sh 文件
sh_files=$(ls ${SCRIPTS_DIR}/*.sh 2> /dev/null | wc -l)
if [ "$sh_files" != "0" ]; then
    # 为每个 .sh 文件创建一个新的 ConfigMap
    CMD="kubectl create configmap ${CONFIGMAP_NAME}"
    for file in ${SCRIPTS_DIR}/*.sh
    do
        CMD="${CMD} --from-file=${file}"
    done
    $CMD
else
    echo "No .sh files found in the directory."
fi
