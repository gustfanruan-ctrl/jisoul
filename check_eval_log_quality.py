import json
import pathlib
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("43.252.230.38", username="root", password="SJRZWcajug09", timeout=20)

# 1) latest file in container
cmd_latest = "docker exec jisoul-backend sh -lc 'ls -1t /app/logs/rag_eval_basic_*.jsonl 2>/dev/null'"
stdin, stdout, stderr = ssh.exec_command(cmd_latest, get_pty=True, timeout=60)
paths = [x.strip() for x in stdout.read().decode("utf-8", "ignore").splitlines() if x.strip()]
_ = stderr.read().decode("utf-8", "ignore")
if not paths:
    print(json.dumps({"ok": False, "error": "no rag_eval_basic jsonl found"}, ensure_ascii=False))
    ssh.close()
    raise SystemExit(0)
latest = paths[0]

# 2) copy latest log from container to host
host_copy = f"/opt/jisoul/backend/logs/latest_rag_eval_copy.jsonl"
cmd_copy = f"docker cp jisoul-backend:{latest} {host_copy}"
stdin, stdout, stderr = ssh.exec_command(cmd_copy, get_pty=True, timeout=120)
_ = stdout.read().decode("utf-8", "ignore")
err = stderr.read().decode("utf-8", "ignore")
if err.strip():
    print(json.dumps({"ok": False, "error": err.strip(), "latest": latest}, ensure_ascii=False))
    ssh.close()
    raise SystemExit(0)

# 3) download to local and validate
local_copy = pathlib.Path("D:/jisoul/backend/logs/latest_rag_eval_copy.jsonl")
local_copy.parent.mkdir(parents=True, exist_ok=True)
sftp = ssh.open_sftp()
sftp.get(host_copy, str(local_copy))
sftp.close()
ssh.close()

lines = local_copy.read_text(encoding="utf-8", errors="replace").splitlines()
total = len(lines)
valid = 0
invalid = 0
missing_case = 0
empty_top = 0
duplicate_pairs = 0
seen = set()
samples = []

for ln in lines[:5000]:
    try:
        obj = json.loads(ln)
        valid += 1
        if not obj.get("case_id"):
            missing_case += 1
        tr = obj.get("top_results") or []
        if len(tr) == 0:
            empty_top += 1
        key = (obj.get("case_id"), obj.get("query"))
        if key in seen:
            duplicate_pairs += 1
        else:
            seen.add(key)
        if len(samples) < 3:
            samples.append(
                {
                    "case_id": obj.get("case_id"),
                    "metrics": obj.get("metrics"),
                    "top_result_count": len(tr),
                    "top_result_preview": (tr[0].get("content_preview") if tr else None),
                }
            )
    except Exception:
        invalid += 1

print(
    json.dumps(
        {
            "ok": True,
            "source_container_file": latest,
            "local_copy": str(local_copy),
            "total_lines": total,
            "checked_lines": min(total, 5000),
            "valid_json_lines": valid,
            "invalid_json_lines": invalid,
            "missing_case_id": missing_case,
            "empty_top_results": empty_top,
            "duplicate_case_query_pairs": duplicate_pairs,
            "samples": samples,
        },
        ensure_ascii=False,
        indent=2,
    )
)
