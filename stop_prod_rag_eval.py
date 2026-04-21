"""在生产容器 jisoul-backend 内终止 rag_eval.py 进程。"""
from __future__ import annotations

import pathlib
import re

import paramiko

REPO = pathlib.Path(__file__).resolve().parent
t = (REPO / "check_eval_log_quality.py").read_text(encoding="utf-8")
m = re.search(r'ssh\.connect\("([^"]+)",\s*username="([^"]+)",\s*password="([^"]+)"', t)
assert m
h, u, p = m.groups()
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(h, username=u, password=p, timeout=25)
cmd = (
    "bash -lc '"
    "docker exec jisoul-backend sh -lc \"pkill -f rag_eval.py 2>/dev/null || true; "
    "pkill -f /app/scripts/rag_eval.py 2>/dev/null || true\"; "
    "PIDS=$(docker top jisoul-backend -eo pid,cmd | grep -E \"rag_eval\\.py\" | grep -v grep | awk \"{print $1}\"); "
    "for p in $PIDS; do kill -9 $p 2>/dev/null || true; done; "
    "sleep 1; "
    "docker top jisoul-backend -eo pid,cmd | grep -E \"rag_eval\\.py\" | grep -v grep || true; "
    "echo done'"
)
_, o, e = c.exec_command(cmd, timeout=45)
print(o.read().decode("utf-8", errors="replace"))
print(e.read().decode("utf-8", errors="replace"))
c.close()
