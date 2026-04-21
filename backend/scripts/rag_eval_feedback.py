"""离线：从已有 rag_eval jsonl 生成知识库改进反馈 JSON。

不调用 LLM；与 app.services.rag_eval_feedback 一致，仅规则聚合。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.rag_eval_feedback import write_feedback_json  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="Build RAG eval → knowledge feedback JSON")
    p.add_argument("--detail-jsonl", required=True, type=Path)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--metrics-json", type=Path, default=None, help="optional summary JSON for metrics_snapshot")
    args = p.parse_args()

    rows = []
    with args.detail_jsonl.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))

    metrics = {}
    if args.metrics_json and args.metrics_json.exists():
        metrics = json.loads(args.metrics_json.read_text(encoding="utf-8")).get("metrics") or {}

    run_id = rows[0].get("run_id", "unknown") if rows else "empty"
    out = args.out or args.detail_jsonl.with_name(args.detail_jsonl.stem + "_feedback.json")
    write_feedback_json(rows, metrics, out, run_id=str(run_id))
    print(json.dumps({"ok": True, "feedback_json": str(out), "rows": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
