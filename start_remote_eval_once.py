import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("43.252.230.38", username="root", password="SJRZWcajug09", timeout=20)

cmd = (
    "cd /opt/jisoul/backend; "
    "mkdir -p logs scripts data; "
    "pkill -f \"scripts/rag_eval.py --cases data/rag_eval_cases.auto.json\" || true; "
    "/opt/jisoul/backend/venv/bin/python scripts/generate_rag_cases.py --count 2000 --output data/rag_eval_cases.auto.json >> logs/rag_eval_batch_start.log 2>&1; "
    "nohup /opt/jisoul/backend/venv/bin/python scripts/rag_eval.py --cases data/rag_eval_cases.auto.json --engine basic --top-k 10 --duration-hours 8 --interval-seconds 30 --output-dir logs >> logs/rag_eval_batch_start.log 2>&1 < /dev/null & "
    "echo PID:$!; "
    "sleep 1; "
    "ps -ef | grep \"scripts/rag_eval.py\" | grep -v grep || true; "
    "tail -n 20 logs/rag_eval_batch_start.log || true"
)

stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True, timeout=180)
print(stdout.read().decode("utf-8", "ignore"))
print(stderr.read().decode("utf-8", "ignore"))
ssh.close()
