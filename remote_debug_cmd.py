import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("43.252.230.38", username="root", password="SJRZWcajug09", timeout=20)

cmd = "cd /opt/jisoul/backend; pwd; ls -la; which python; python --version; mkdir -p logs; echo hello >> logs/rag_eval_batch_start.log; tail -n 5 logs/rag_eval_batch_start.log"
stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True, timeout=120)
print("OUT:")
print(stdout.read().decode("utf-8", "ignore"))
print("ERR:")
print(stderr.read().decode("utf-8", "ignore"))
print("EXIT:", stdout.channel.recv_exit_status())
ssh.close()
