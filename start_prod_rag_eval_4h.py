"""
在生产机 Docker 容器 jisoul-backend 内：同步脚本 → 生成用例 → 后台跑 4h RAG batch。

（宿主机 /opt/jisoul/backend 无 venv 时仅有 Python2，评测实际在容器 /app 内执行。）

SSH 凭据从 check_eval_log_quality.py 解析。
"""
from __future__ import annotations

import pathlib
import re
import sys

import paramiko

REPO_ROOT = pathlib.Path(__file__).resolve().parent
CRED_PATH = REPO_ROOT / "check_eval_log_quality.py"
REMOTE_SCRIPTS = "/opt/jisoul/backend/scripts"
CONTAINER = "jisoul-backend"
DURATION_H = 4


def _creds(path: pathlib.Path) -> tuple[str, str, str]:
    t = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r'ssh\.connect\("([^"]+)",\s*username="([^"]+)",\s*password="([^"]+)"', t)
    if not m:
        raise SystemExit(f"cannot parse creds from {path}")
    return m.group(1), m.group(2), m.group(3)


def main() -> None:
    log = REPO_ROOT / "_prod_eval_start.log"

    def logln(msg: str) -> None:
        with log.open("a", encoding="utf-8") as f:
            f.write(msg + "\n")

    log.write_text("", encoding="utf-8")
    host, user, password = _creds(CRED_PATH)
    logln(f"connecting {host} as {user}")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=user, password=password, timeout=30)

    sftp = ssh.open_sftp()
    for name in ("rag_eval.py", "generate_rag_cases.py"):
        local = REPO_ROOT / "backend" / "scripts" / name
        sftp.put(str(local), f"{REMOTE_SCRIPTS}/{name}")
        logln(f"put host:{REMOTE_SCRIPTS}/{name}")
    sftp.close()

    # 与仓库部署路径一致：/opt/jisoul/backend → docker cp backend/scripts/...
    cmd = (
        f"docker cp {REMOTE_SCRIPTS}/rag_eval.py {CONTAINER}:/app/scripts/rag_eval.py && "
        f"docker cp {REMOTE_SCRIPTS}/generate_rag_cases.py {CONTAINER}:/app/scripts/generate_rag_cases.py && "
        f"docker exec {CONTAINER} mkdir -p /app/logs /app/data /app/scripts && "
        f"docker exec {CONTAINER} sh -lc "
        f"'python /app/scripts/generate_rag_cases.py --count 2000 --output /app/data/rag_eval_cases.auto.json "
        f"> /app/logs/rag_eval_gen.log 2>&1; echo GEN_EXIT:$?; tail -n 5 /app/logs/rag_eval_gen.log' && "
        f"docker exec {CONTAINER} sh -lc "
        f"'nohup python /app/scripts/rag_eval.py --cases /app/data/rag_eval_cases.auto.json "
        f"--engine basic --top-k 10 --duration-hours {DURATION_H} --interval-seconds 30 --output-dir /app/logs "
        f">> /app/logs/rag_eval_batch_start.log 2>&1 </dev/null &' && "
        "sleep 12 && "
        f"docker exec {CONTAINER} sh -lc \"command -v pgrep >/dev/null && pgrep -af rag_eval.py || echo NO_PGREP\" && "
        f"docker exec {CONTAINER} sh -lc \"ls -lt /app/logs | head -n 12\" && "
        f"docker exec {CONTAINER} sh -lc \"tail -n 25 /app/logs/rag_eval_batch_start.log 2>/dev/null || echo NO_BATCH_LOG\""
    )

    logln("exec docker pipeline")
    _, stdout, stderr = ssh.exec_command(cmd, get_pty=False, timeout=600)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if code == -1:
        code = 0
    logln(out)
    if err.strip():
        logln("stderr:\n" + err.strip())
    print(out)
    if err.strip():
        print(err, file=sys.stderr)
    ok_gen = "GEN_EXIT:0" in out or "generated=2000" in out
    if not ok_gen:
        code = 1
        logln("generate step may have failed")
    ssh.close()
    logln(f"exit_code={code}")
    raise SystemExit(code)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log = REPO_ROOT / "_prod_eval_start.log"
        with log.open("a", encoding="utf-8") as f:
            import traceback

            traceback.print_exc(file=f)
        raise
