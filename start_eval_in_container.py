import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("43.252.230.38", username="root", password="SJRZWcajug09", timeout=20)

cmd = """
cd /opt/jisoul
docker exec jisoul-backend mkdir -p /app/logs /app/data /app/scripts
docker cp backend/scripts/rag_eval.py jisoul-backend:/app/scripts/rag_eval.py
docker cp backend/scripts/generate_rag_cases.py jisoul-backend:/app/scripts/generate_rag_cases.py
docker exec -d jisoul-backend python /app/scripts/generate_rag_cases.py --count 2000 --output /app/data/rag_eval_cases.auto.json
sleep 2
docker exec -d jisoul-backend python /app/scripts/rag_eval.py --cases /app/data/rag_eval_cases.auto.json --engine basic --top-k 10 --duration-hours 8 --interval-seconds 30 --output-dir /app/logs
sleep 2
docker exec jisoul-backend sh -lc "ls -la /app/logs"
docker exec jisoul-backend sh -lc "ls -la /app/data"
"""

stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True, timeout=240)
print(stdout.read().decode("utf-8", "ignore"))
print(stderr.read().decode("utf-8", "ignore"))
ssh.close()
