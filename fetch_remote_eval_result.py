import json
import pathlib
import re

import paramiko

t = pathlib.Path("D:/jisoul/check_eval_log_quality.py").read_text(encoding="utf-8")
m = re.search(r'ssh\.connect\("([^"]+)",\s*username="([^"]+)",\s*password="([^"]+)"', t)
assert m
h, u, p = m.groups()

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(h, username=u, password=p, timeout=25)

cmd = (
    "docker exec jisoul-backend python -c "
    "\"import os,json; p='/app/logs'; fs=os.listdir(p); "
    "runs=sorted([x for x in fs if x.startswith('rag_eval_basic_20260421_') and x.endswith('_summary.json')]); "
    "batches=sorted([x for x in fs if x.startswith('rag_eval_batch_basic_20260421_') and x.endswith('_summary.json')]); "
    "d={'latest_run': runs[-1] if runs else '', 'latest_batch': batches[-1] if batches else ''}; "
    "import io; "
    "print(json.dumps(d, ensure_ascii=False)); "
    "print('SPLIT_MARKER'); "
    "print(open(os.path.join(p,d['latest_run'])).read() if d['latest_run'] else ''); "
    "print('SPLIT_MARKER2'); "
    "print(open(os.path.join(p,d['latest_batch'])).read() if d['latest_batch'] else '')\""
)
_, o, e = ssh.exec_command(cmd, timeout=90)
out = o.read().decode("utf-8", errors="replace")
err = e.read().decode("utf-8", errors="replace")
ssh.close()

print(out)
if err.strip():
    print("ERR:", err)
