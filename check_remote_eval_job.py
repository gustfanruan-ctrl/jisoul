import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("43.252.230.38", username="root", password="SJRZWcajug09", timeout=20)

cmd = (
    "cd /opt/jisoul/backend; "
    "echo '---files---'; "
    "ls -la scripts || true; "
    "echo '---ps---'; "
    "ps -ef | grep 'scripts/rag_eval.py' | grep -v grep || true; "
    "echo '---log tail---'; "
    "tail -n 40 logs/rag_eval_batch_start.log 2>/dev/null || echo 'no log yet'"
)
stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True, timeout=120)
print(stdout.read().decode("utf-8", "ignore"))
print(stderr.read().decode("utf-8", "ignore"))
ssh.close()
