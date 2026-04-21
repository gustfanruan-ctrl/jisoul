import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("43.252.230.38", username="root", password="SJRZWcajug09", timeout=20)

cmd = """
docker exec jisoul-backend sh -lc "ls -la /app/logs"
docker exec jisoul-backend sh -lc "ls -la /app/logs | grep rag_eval || true"
docker exec jisoul-backend sh -lc "test -f /app/logs/rag_eval_batch_start.log && tail -n 20 /app/logs/rag_eval_batch_start.log || echo no_start_log"
"""

stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True, timeout=120)
print(stdout.read().decode("utf-8", "ignore"))
print(stderr.read().decode("utf-8", "ignore"))
ssh.close()
