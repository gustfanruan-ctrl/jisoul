"""
Pull RAG eval artifacts from production (Docker jisoul-backend) to this machine.

SSH credentials are read from check_eval_log_quality.py (same pattern as other
maintainer scripts in this repo) — no duplicate secret in this file.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

import paramiko

REPO_ROOT = pathlib.Path(__file__).resolve().parent
CRED_PATH = REPO_ROOT / "check_eval_log_quality.py"
CONTAINER = "jisoul-backend"
REMOTE_TMP = "/opt/jisoul/backend/logs/_prod_sync_tmp"
LOCAL_BASE = REPO_ROOT / "backend" / "logs" / "from_prod"


def _load_ssh_creds(path: pathlib.Path) -> tuple[str, str, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(
        r'ssh\.connect\("([^"]+)",\s*username="([^"]+)",\s*password="([^"]+)"',
        text,
    )
    if not m:
        raise SystemExit(f"cannot parse ssh.connect() from {path}")
    return m.group(1), m.group(2), m.group(3)


def _ssh_exec(ssh: paramiko.SSHClient, cmd: str, timeout: int = 300) -> tuple[int, str, str]:
    stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return stdout.channel.recv_exit_status(), out, err


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--date-prefix",
        default="",
        help="If set (e.g. 20260421), only sync files whose names contain this substring.",
    )
    p.add_argument(
        "--cred-file",
        type=pathlib.Path,
        default=CRED_PATH,
        help="Python file containing ssh.connect(host, user, password=...).",
    )
    args = p.parse_args()

    host, user, password = _load_ssh_creds(args.cred_file)

    list_cmd = (
        f"docker exec {CONTAINER} sh -lc "
        f"'ls -1 /app/logs 2>/dev/null | grep -E \"^rag_eval\" || true'"
    )
    mkdir_cmd = f"mkdir -p {REMOTE_TMP} && rm -f {REMOTE_TMP}/*"

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=user, password=password, timeout=30)

    code, out, err = _ssh_exec(ssh, mkdir_cmd, timeout=60)
    if code != 0:
        print(err or out, file=sys.stderr)
        ssh.close()
        raise SystemExit(f"remote mkdir failed: exit {code}")

    code, out, err = _ssh_exec(ssh, list_cmd, timeout=120)
    if code != 0:
        print(err or out, file=sys.stderr)
        ssh.close()
        raise SystemExit(f"remote list failed: exit {code}")

    names = [x.strip() for x in out.splitlines() if x.strip()]
    if args.date_prefix:
        names = [n for n in names if args.date_prefix in n]
    if not names:
        print("no matching files in container /app/logs", file=sys.stderr)
        ssh.close()
        raise SystemExit(2)

    LOCAL_BASE.mkdir(parents=True, exist_ok=True)
    sftp = ssh.open_sftp()

    ok, fail = [], []
    for name in sorted(names):
        remote_container_path = f"/app/logs/{name}"
        remote_host_path = f"{REMOTE_TMP}/{name}"
        local_path = LOCAL_BASE / name
        cp = f"docker cp {CONTAINER}:{remote_container_path} {remote_host_path}"
        c, o, e = _ssh_exec(ssh, cp, timeout=600)
        if c != 0:
            fail.append((name, (e or o or "").strip()))
            continue
        try:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            sftp.get(remote_host_path, str(local_path))
            ok.append(name)
        except Exception as ex:  # noqa: BLE001
            fail.append((name, str(ex)))

    sftp.close()
    ssh.close()

    print(f"synced {len(ok)} files -> {LOCAL_BASE}")
    for n in ok:
        print(f"  ok: {n}")
    if fail:
        print(f"failed {len(fail)}:", file=sys.stderr)
        for n, msg in fail:
            print(f"  {n}: {msg}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
