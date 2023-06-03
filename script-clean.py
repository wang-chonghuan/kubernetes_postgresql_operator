import subprocess

commands = [
    "kubectl delete sts pgset",
    "kubectl delete pvc pgdata-pgset-0",
    "kubectl delete pvc pgdata-pgset-1",
    "kubectl delete pv pv-pg-0",
    "kubectl delete pv pv-pg-1",
]

for cmd in commands:
    process = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE)
    output, error = process.communicate()

    if process.returncode != 0:
        print(f"Error executing command: {cmd}\nError: {error}")
    else:
        print(f"Executed command: {cmd}\nOutput: {output}")
