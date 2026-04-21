"""组合评测用例生成。

设计原则（防过拟合 / 零 LLM）：
- 本脚本不调用大模型；baseline 仅来自「检索快照」，语义上不是金标，只用于回归对比。
- 默认只锚定少量 chunk（baseline_top_k 默认 1），避免把整条粗排曲线写进标签导致对当前排序过拟合。
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

INDUSTRIES = ["通用", "零售", "制造", "金融", "医疗", "教育", "互联网", "电商"]
PRODUCTS = ["FineBI", "FineReport", "FineDataLink", "帆软", "泛BI", "帆report", "finebi", "finereport"]

INTENT_TEMPLATES = {
    "价格异议": [
        "客户觉得 {product} 报价太高，{industry} 行业怎么推进？",
        "{industry} 客户预算有限，{product} 有什么落地建议？",
    ],
    "竞品对比": [
        "{product} 和 PowerBI 对比优势是什么？",
        "{product} 跟 Tableau 比，在 {industry} 的优势有哪些？",
    ],
    "功能咨询": [
        "{industry} 场景里，{product} 能做实时驾驶舱吗？",
        "{product} 支持多数据源和权限隔离吗？",
    ],
    "实施落地": [
        "{industry} 企业实施 {product} 一般要多久？",
        "{product} 上线复杂吗，怎么分阶段实施？",
    ],
    "行业场景": [
        "{industry} 的典型数据分析场景，{product} 怎么应用？",
        "{industry} 从报表到看板通常怎么建设？",
    ],
}

NOISE = ["", " 请给可以复述的话术。", " 客户比较强势，语气要稳。", " 先不要太技术化。"]


def make_case(i: int, rng: random.Random) -> dict:
    industry = rng.choice(INDUSTRIES)
    product = rng.choice(PRODUCTS)
    intent = rng.choice(list(INTENT_TEMPLATES.keys()))
    query = rng.choice(INTENT_TEMPLATES[intent]).format(industry=industry, product=product) + rng.choice(NOISE)
    return {
        "id": f"auto_{i:06d}",
        "query": query,
        "industry": industry,
        "intent_hint": intent,
        "expected_chunk_ids": [],
        "expected_keywords": [intent, industry, product],
    }


def _fill_baseline_for_cases(
    cases: list[dict],
    *,
    baseline_engine: str,
    baseline_top_k: int,
) -> None:
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from app.knowledge.store import vector_store  # noqa: E402
    from app.services.metadata_enhanced_search import metadata_enhanced_search  # noqa: E402
    from app.services.rag_service import rag_service  # noqa: E402
    from app.services.rag_service_enhanced import rag_service_enhanced  # noqa: E402

    def search(engine: str, query: str, industry: str, top_k: int) -> list:
        if engine == "basic":
            return rag_service.search(query=query, industry=industry, top_k=top_k, enable_rerank=False)
        if engine == "enhanced":
            return rag_service_enhanced.search(
                query=query,
                industry=industry,
                top_k=top_k,
                enable_rerank=False,
                enable_intent_filter=True,
            )
        if engine == "metadata":
            return metadata_enhanced_search.search(
                query=query,
                industry=industry,
                top_k=top_k,
                enable_rerank=False,
                enable_intent_filter=True,
                enable_keyword_match=True,
                enable_priority_weight=True,
            )
        raise ValueError(f"unknown baseline engine: {engine}")

    vector_store.init()
    cap_at = datetime.now(timezone.utc).isoformat()
    for c in cases:
        res = search(baseline_engine, str(c["query"]), str(c.get("industry") or "通用"), baseline_top_k)
        ids = [str(x.get("chunk_id") or "") for x in res if x.get("chunk_id")]
        c["baseline_chunk_ids"] = ids
        c["baseline_engine"] = baseline_engine
        c["baseline_top_k"] = baseline_top_k
        c["eval_spec_version"] = 2
        c["baseline_captured_at"] = cap_at


def main() -> None:
    p = argparse.ArgumentParser(description="Generate combinational RAG eval cases")
    p.add_argument("--count", type=int, default=1000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output", default="data/rag_eval_cases.auto.json")
    p.add_argument(
        "--fill-baseline",
        action="store_true",
        help="对每条用例调用检索写入 baseline_chunk_ids：仅作检索回归锚点，不是语义金标；请勿用 LLM 伪造内容对齐该锚点。",
    )
    p.add_argument("--baseline-engine", default="basic", choices=["basic", "enhanced", "metadata"])
    p.add_argument(
        "--baseline-top-k",
        type=int,
        default=1,
        help="写入 baseline 的前 K 条 chunk_id；默认 1 以降低对当前粗排/切片的自举过拟合，需要更宽锚点可调到 3–5。",
    )
    args = p.parse_args()

    if args.fill_baseline and args.baseline_top_k > 3:
        print(
            "warning: baseline_top_k>3 会增强「对当前检索曲线的记忆」，更易过拟合；若无充分理由建议保持 1–3。",
            file=sys.stderr,
        )

    rng = random.Random(args.seed)
    cases = [make_case(i + 1, rng) for i in range(args.count)]
    if args.fill_baseline:
        _fill_baseline_for_cases(
            cases,
            baseline_engine=args.baseline_engine,
            baseline_top_k=args.baseline_top_k,
        )
        bundle = {
            "eval_bundle_version": 2,
            "baseline": {
                "engine": args.baseline_engine,
                "top_k": args.baseline_top_k,
                "captured_at": datetime.now(timezone.utc).isoformat(),
            },
            "eval_constraints": {
                "llm_involved": False,
                "baseline_semantics": "retrieval_snapshot_only_not_human_gold",
                "anti_overfitting": "minimal_baseline_ids_default_top1_do_not_tune_kb_solely_to_baseline",
            },
            "cases": cases,
        }
        out_obj: dict | list = bundle
    else:
        out_obj = cases

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(out_obj, f, ensure_ascii=False, indent=2)
    print(f"generated={len(cases)} output={out} fill_baseline={bool(args.fill_baseline)}")


if __name__ == "__main__":
    main()
