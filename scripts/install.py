import subprocess
import time

path = "../src"
commands = [
    f"bash ./upload-configmap.sh {path}/configmap", #上传statefulset启动脚本
    f"kubectl apply -f {path}/configmap/pgpool-configmap.yaml", #上传pgpool2启动参数
    f"kubectl apply -f {path}/secret/spok-secret.yaml", #上传数据库密码
    #f"kubectl apply -f {path}/storage/pv-0.yaml", #创建主库PV
    #f"kubectl apply -f {path}/storage/pv-1.yaml", #创建从库PV
    #f"kubectl apply -f {path}/service/headless-service.yaml", #创建DNS命名服务
    #f"kubectl apply -f {path}/statefulset/pg-sts-master.yaml", #创建主库statefulset
    #f"kubectl apply -f {path}/statefulset/pg-sts-replica.yaml", #创建从库statefulset
    f"kubectl apply -f {path}/operator/spok_cr.yaml", # create cluster
    f"kubectl apply -f {path}/gateway/pgpool-deploy.yaml" #创建pgpool2 deployment
]

for cmd in commands:
    process = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE)
    output, error = process.communicate()

    if process.returncode != 0:
        print(f"Error executing command: {cmd}\nError: {error}")
    else:
        print(f"Executed command: {cmd}\nOutput: {output}")
    
    time.sleep(1)
