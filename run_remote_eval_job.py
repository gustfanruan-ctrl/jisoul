import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("43.252.230.38", username="root", password="SJRZWcajug09", timeout=20)

remote_cmd = """
bash -lc '
  cd /opt/jisoul/backend
  mkdir -p logs
  pkill -f "scripts/rag_eval.py --cases data/rag_eval_cases.auto.json" || true
  python scripts/generate_rag_cases.py --count 2000 --output data/rag_eval_cases.auto.json >> logs/rag_eval_batch_start.log 2>&1
  nohup python scripts/rag_eval.py --cases data/rag_eval_cases.auto.json --engine basic --top-k 10 --duration-hours 8 --interval-seconds 30 --output-dir logs >> logs/rag_eval_batch_start.log 2>&1 &
  echo STARTED:$!
'
"""

stdin, stdout, stderr = ssh.exec_command(remote_cmd, get_pty=True, timeout=120)
out = stdout.read().decode("utf-8", "ignore")
err = stderr.read().decode("utf-8", "ignore")
code = stdout.channel.recv_exit_status()
print(out)
print(err)
print(f"exit_code={code}")
ssh.close()
