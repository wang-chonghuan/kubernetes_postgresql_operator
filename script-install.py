import subprocess

commands = [
    "kubectl apply -f pv-0.yaml",
    "kubectl apply -f pv-1.yaml",
    "kubectl apply -f headless-service.yaml",
    "kubectl apply -f pg-sts-master.yaml",
    "kubectl apply -f pg-sts-replica.yaml",
]

for cmd in commands:
    process = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE)
    output, error = process.communicate()

    if process.returncode != 0:
        print(f"Error executing command: {cmd}\nError: {error}")
    else:
        print(f"Executed command: {cmd}\nOutput: {output}")
