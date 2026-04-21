"""RAG 检索评测（无 LLM 生成、无 LLM 打分）。

指标仅基于 chunk_id / 关键词字面匹配与（可选）检索快照 baseline，避免模型评委带来的
目标泄漏与过拟合。baseline 来自 generate_rag_cases --fill-baseline 时同一检索链路的快照，
只应用作工程回归，不等同于人工金标。
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.knowledge.store import vector_store  # noqa: E402
from app.services.metadata_enhanced_search import metadata_enhanced_search  # noqa: E402
from app.services.rag_service import rag_service  # noqa: E402
from app.services.rag_service_enhanced import rag_service_enhanced  # noqa: E402

try:
    from app.services.rag_eval_feedback import write_feedback_json  # noqa: E402
except ImportError:
    write_feedback_json = None  # 容器镜像未同步该模块时仍可跑评测主流程


def _load_cases(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "cases" in data:
        meta = {k: v for k, v in data.items() if k != "cases"}
        return data["cases"], meta
    if isinstance(data, list):
        return data, None
    raise ValueError('cases file must be a JSON array or {"cases": [...]} object')


def _search(engine: str, query: str, industry: str, top_k: int, enable_rerank: bool) -> list[dict[str, Any]]:
    if engine == "basic":
        return rag_service.search(query=query, industry=industry, top_k=top_k, enable_rerank=enable_rerank)
    if engine == "enhanced":
        return rag_service_enhanced.search(
            query=query,
            industry=industry,
            top_k=top_k,
            enable_rerank=enable_rerank,
            enable_intent_filter=True,
        )
    if engine == "metadata":
        return metadata_enhanced_search.search(
            query=query,
            industry=industry,
            top_k=top_k,
            enable_rerank=enable_rerank,
            enable_intent_filter=True,
            enable_keyword_match=True,
            enable_priority_weight=True,
        )
    raise ValueError(f"unknown engine: {engine}")


def _hit_at_k(expected: list[str], predicted: list[str], k: int) -> int:
    if not expected:
        return 0
    exp = {x.strip().lower() for x in expected}
    top = {x.strip().lower() for x in predicted[:k]}
    return int(bool(exp & top))


def _rank(expected: list[str], predicted: list[str]) -> int | None:
    if not expected:
        return None
    exp = {x.strip().lower() for x in expected}
    for i, p in enumerate(predicted, start=1):
        if p.strip().lower() in exp:
            return i
    return None


def _keyword_hit_at_k(expected_keywords: list[str], predicted_texts: list[str], k: int) -> int:
    if not expected_keywords:
        return 0
    text = "\n".join(predicted_texts[:k]).lower()
    return int(any(kw.strip().lower() in text for kw in expected_keywords))


def _baseline_recall_at_k(baseline: list[str], predicted: list[str], k: int) -> float:
    bset = {str(x).strip().lower() for x in baseline if str(x).strip()}
    if not bset:
        return 0.0
    pset = {str(x).strip().lower() for x in predicted[:k] if str(x).strip()}
    return round(len(bset & pset) / len(bset), 4)


def run_once(
    cases: list[dict[str, Any]],
    engine: str,
    top_k: int,
    enable_rerank: bool,
    output_dir: Path,
    init_store: bool = True,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = f"rag_eval_{engine}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    detail = output_dir / f"{run_id}.jsonl"
    summary_file = output_dir / f"{run_id}_summary.json"

    if init_store:
        vector_store.init()

    hit1, hit3, hit5, hit10, mrr = [], [], [], [], []
    kw3, kw5, kw10 = [], [], []
    bh1, bh3, bh10, br10, bmrr = [], [], [], [], []
    feedback_rows: list[dict[str, Any]] = []

    with detail.open("w", encoding="utf-8") as f:
        for i, c in enumerate(cases, start=1):
            query = str(c["query"])
            industry = str(c.get("industry") or "通用")
            intent_hint = str(c.get("intent_hint") or "")
            expected_ids = [str(x) for x in c.get("expected_chunk_ids", [])]
            baseline_ids = [str(x) for x in c.get("baseline_chunk_ids", []) if str(x).strip()]
            expected_keywords = [str(x) for x in c.get("expected_keywords", [])]

            res = _search(engine, query, industry, top_k, enable_rerank)
            ids = [str(x.get("chunk_id") or "") for x in res]
            texts = [str(x.get("content") or "") for x in res]

            r = _rank(expected_ids, ids)
            h1 = _hit_at_k(expected_ids, ids, 1)
            h3 = _hit_at_k(expected_ids, ids, 3)
            h5 = _hit_at_k(expected_ids, ids, 5)
            h10 = _hit_at_k(expected_ids, ids, 10)
            m = 1.0 / r if r else 0.0
            k3 = _keyword_hit_at_k(expected_keywords, texts, 3)
            k5 = _keyword_hit_at_k(expected_keywords, texts, 5)
            k10 = _keyword_hit_at_k(expected_keywords, texts, 10)

            hit1.append(h1), hit3.append(h3), hit5.append(h5), hit10.append(h10), mrr.append(m)
            kw3.append(k3), kw5.append(k5), kw10.append(k10)

            metrics_row: dict[str, Any] = {
                "hit@1": h1,
                "hit@3": h3,
                "hit@5": h5,
                "hit@10": h10,
                "mrr": round(m, 4),
                "keyword_hit@3": k3,
                "keyword_hit@5": k5,
                "keyword_hit@10": k10,
            }
            if baseline_ids:
                br = _rank(baseline_ids, ids)
                b_m = 1.0 / br if br else 0.0
                b1 = _hit_at_k(baseline_ids, ids, 1)
                b3 = _hit_at_k(baseline_ids, ids, 3)
                b10 = _hit_at_k(baseline_ids, ids, 10)
                metrics_row["baseline_hit@1"] = b1
                metrics_row["baseline_hit@3"] = b3
                metrics_row["baseline_hit@10"] = b10
                metrics_row["baseline_recall@10"] = _baseline_recall_at_k(baseline_ids, ids, 10)
                metrics_row["baseline_mrr"] = round(b_m, 4)
                bh1.append(b1)
                bh3.append(b3)
                bh10.append(b10)
                br10.append(metrics_row["baseline_recall@10"])
                bmrr.append(b_m)

            record = {
                "ts": datetime.now().isoformat(timespec="seconds"),
                "run_id": run_id,
                "case_id": c.get("id", f"case_{i}"),
                "query": query,
                "industry": industry,
                "intent_hint": intent_hint,
                "metrics": metrics_row,
                "top_results": [
                    {
                        "rank": idx + 1,
                        "chunk_id": x.get("chunk_id"),
                        "score": x.get("score"),
                        "rerank_score": x.get("rerank_score"),
                        "type": (x.get("metadata") or {}).get("type"),
                        "content_preview": str(x.get("content") or "")[:160],
                    }
                    for idx, x in enumerate(res[:top_k])
                ],
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            feedback_rows.append(record)

    metrics_summary: dict[str, Any] = {
        "hit@1": round(statistics.mean(hit1) if hit1 else 0.0, 4),
        "hit@3": round(statistics.mean(hit3) if hit3 else 0.0, 4),
        "hit@5": round(statistics.mean(hit5) if hit5 else 0.0, 4),
        "hit@10": round(statistics.mean(hit10) if hit10 else 0.0, 4),
        "mrr": round(statistics.mean(mrr) if mrr else 0.0, 4),
        "keyword_hit@3": round(statistics.mean(kw3) if kw3 else 0.0, 4),
        "keyword_hit@5": round(statistics.mean(kw5) if kw5 else 0.0, 4),
        "keyword_hit@10": round(statistics.mean(kw10) if kw10 else 0.0, 4),
    }
    if bh10:
        metrics_summary["baseline_eval_cases"] = len(bh10)
        metrics_summary["baseline_hit@1"] = round(statistics.mean(bh1), 4)
        metrics_summary["baseline_hit@3"] = round(statistics.mean(bh3), 4)
        metrics_summary["baseline_hit@10"] = round(statistics.mean(bh10), 4)
        metrics_summary["baseline_recall@10"] = round(statistics.mean(br10), 4)
        metrics_summary["baseline_mrr"] = round(statistics.mean(bmrr), 4)

    artifacts: dict[str, str] = {
        "detail_jsonl": str(detail),
        "summary_json": str(summary_file),
    }
    if write_feedback_json is not None:
        feedback_path = output_dir / f"{run_id}_feedback.json"
        write_feedback_json(feedback_rows, metrics_summary, feedback_path, run_id=run_id)
        artifacts["feedback_json"] = str(feedback_path)

    summary = {
        "run_id": run_id,
        "engine": engine,
        "top_k": top_k,
        "enable_rerank": enable_rerank,
        "cases_total": len(cases),
        "metrics": metrics_summary,
        "artifacts": artifacts,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    with summary_file.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return summary


def run_duration(
    cases: list[dict[str, Any]],
    engine: str,
    top_k: int,
    enable_rerank: bool,
    output_dir: Path,
    duration_hours: float,
    interval_seconds: int,
) -> dict[str, Any]:
    batch_id = f"rag_eval_batch_{engine}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    aggregate = output_dir / f"{batch_id}_aggregate.jsonl"
    end_at = datetime.now() + timedelta(hours=duration_hours)
    runs = 0
    summaries = []
    vector_store.init()
    while datetime.now() < end_at:
        runs += 1
        s = run_once(cases, engine, top_k, enable_rerank, output_dir, init_store=False)
        summaries.append(s)
        with aggregate.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"batch_id": batch_id, "run_index": runs, "summary": s}, ensure_ascii=False) + "\n")
        if datetime.now() >= end_at:
            break
        time.sleep(max(0, interval_seconds))

    key_union: set[str] = set()
    for s in summaries:
        key_union |= set(s.get("metrics", {}).keys())
    key_union.discard("baseline_eval_cases")
    agg: dict[str, Any] = {}
    for k in sorted(key_union):
        vals = []
        for x in summaries:
            v = x.get("metrics", {}).get(k)
            if v is None:
                continue
            vals.append(float(v))
        agg[k] = round(statistics.mean(vals), 4) if vals else 0.0
    batch_summary = {
        "batch_id": batch_id,
        "runs_completed": runs,
        "duration_hours": duration_hours,
        "interval_seconds": interval_seconds,
        "aggregate_metrics_mean": agg,
        "artifacts": {"aggregate_jsonl": str(aggregate)},
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    out = output_dir / f"{batch_id}_summary.json"
    with out.open("w", encoding="utf-8") as f:
        json.dump(batch_summary, f, ensure_ascii=False, indent=2)
    batch_summary["artifacts"]["batch_summary_json"] = str(out)
    return batch_summary


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="RAG eval script (no LLM generation)")
    p.add_argument("--cases", required=True)
    p.add_argument("--engine", default="basic", choices=["basic", "enhanced", "metadata"])
    p.add_argument("--top-k", type=int, default=10)
    p.add_argument("--enable-rerank", action="store_true", default=False)
    p.add_argument("--output-dir", default=str(ROOT / "logs"))
    p.add_argument("--duration-hours", type=float, default=0.0)
    p.add_argument("--interval-seconds", type=int, default=60)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cases, bundle_meta = _load_cases(Path(args.cases))
    if args.duration_hours and args.duration_hours > 0:
        summary = run_duration(
            cases,
            args.engine,
            args.top_k,
            bool(args.enable_rerank),
            Path(args.output_dir),
            float(args.duration_hours),
            int(args.interval_seconds),
        )
    else:
        summary = run_once(cases, args.engine, args.top_k, bool(args.enable_rerank), Path(args.output_dir))
    if bundle_meta:
        summary["eval_bundle"] = bundle_meta
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

