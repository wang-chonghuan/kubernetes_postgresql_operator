import subprocess

commands = [
    "kubectl delete sts pgset-master --force",
    "kubectl delete sts pgset-replica --force",
    "kubectl delete pvc pgdata-pgset-master-0 pgdata-pgset-replica-0 --force",
    "kubectl delete pv pv-pg-0 pv-pg-1 --force",
    "kubectl delete svc pgsql-headless --force",
]

for cmd in commands:
    process = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE)
    output, error = process.communicate()

    if process.returncode != 0:
        print(f"Error executing command: {cmd}\nError: {error}")
    else:
        print(f"Executed command: {cmd}\nOutput: {output}")
