"""知识库变更 → 重跑 RAG 评测 → 对比指标（闭环中的「库 → 评测」一侧）。

消费 data/kb_eval_signal.jsonl；成功后清空信号，并把摘要写入 data/kb_rag_eval_last_metrics.json
与 data/kb_rag_eval_history.jsonl。

本脚本不调用 LLM；子进程仅运行 rag_eval.py（纯检索与规则指标），避免闭环对生成模型过拟合。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _data(p: str) -> Path:
    return ROOT / "data" / p


def main() -> None:
    p = argparse.ArgumentParser(description="Run RAG eval after KB writes (signal-driven loop)")
    p.add_argument("--cases", default="data/rag_eval_cases.auto.json")
    p.add_argument("--engine", default="basic")
    p.add_argument("--top-k", type=int, default=10)
    p.add_argument("--force", action="store_true", help="即使没有 kb 信号也跑一轮评测")
    args = p.parse_args()

    from app.knowledge.eval_signal import clear_kb_eval_signals, kb_eval_signal_nonempty  # noqa: E402

    if not args.force and not kb_eval_signal_nonempty():
        print(json.dumps({"ok": True, "skipped": True, "reason": "no kb_eval_signal"}, ensure_ascii=False))
        return

    last_path = _data("kb_rag_eval_last_metrics.json")
    prev = {}
    if last_path.exists():
        try:
            prev = json.loads(last_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            prev = {}

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "rag_eval.py"),
        "--cases",
        str(ROOT / args.cases),
        "--engine",
        args.engine,
        "--top-k",
        str(args.top_k),
        "--output-dir",
        str(ROOT / "logs"),
    ]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(proc.returncode)

    summary = json.loads(proc.stdout)
    metrics = summary.get("metrics") or {}

    delta = {}
    for k, v in metrics.items():
        if isinstance(v, (int, float)) and k in prev:
            try:
                delta[k] = round(float(v) - float(prev[k]), 4)
            except (TypeError, ValueError):
                continue

    hist = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "run_id": summary.get("run_id"),
        "metrics": metrics,
        "delta_vs_last": delta,
    }
    hist_path = _data("kb_rag_eval_history.jsonl")
    hist_path.parent.mkdir(parents=True, exist_ok=True)
    with hist_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(hist, ensure_ascii=False) + "\n")

    last_path.write_text(
        json.dumps(
            {
                "ts": hist["ts"],
                "run_id": summary.get("run_id"),
                "metrics": metrics,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    clear_kb_eval_signals()
    print(json.dumps({"ok": True, "summary": summary, "delta_vs_last": delta}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
