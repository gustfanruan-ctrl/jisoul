"""从 RAG 评测明细生成「知识库改进」反馈（闭环中的评测 → 库 一侧）。

刻意保持「零 LLM」：仅用规则统计（关键词命中、baseline 命中、共现计数），不调用大模型
改写、不重写 query、不做模型评委，避免反馈链路对某一 LLM 过拟合或产生伪监督信号。
改进项应由人工抽查后落库，禁止为刷分用 LLM 批量杜撰切片文本对齐 baseline。
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _intent_industry(row: dict[str, Any]) -> tuple[str, str]:
    intent = str(row.get("intent_hint") or row.get("metrics", {}).get("intent_hint") or "未知意图")
    ind = str(row.get("industry") or "未知行业")
    return intent, ind


def build_knowledge_feedback(
    rows: list[dict[str, Any]],
    metrics_snapshot: dict[str, Any] | None = None,
    *,
    max_actions: int = 12,
    max_samples: int = 20,
) -> dict[str, Any]:
    """根据 jsonl 行列表生成可交给运营/研发的改进清单。"""
    total = len(rows)
    if total == 0:
        return {
            "cases_total": 0,
            "knowledge_actions": [],
            "bad_top1_chunks": [],
            "failure_samples": [],
        }

    kw_fail = [r for r in rows if int(r.get("metrics", {}).get("keyword_hit@10", 0)) == 0]
    base_fail = [
        r
        for r in rows
        if r.get("metrics", {}).get("baseline_hit@10") is not None
        and int(r["metrics"]["baseline_hit@10"]) == 0
    ]

    pair_fail = Counter()
    for r in kw_fail:
        intent, ind = _intent_industry(r)
        pair_fail[(intent, ind)] += 1

    top1_on_kw_fail = Counter()
    for r in kw_fail:
        tops = r.get("top_results") or []
        if tops:
            cid = str(tops[0].get("chunk_id") or "")
            if cid:
                top1_on_kw_fail[cid] += 1

    knowledge_actions: list[dict[str, Any]] = []

    for (intent, ind), cnt in pair_fail.most_common(8):
        rate = round(cnt / total, 4)
        knowledge_actions.append(
            {
                "priority": "P1" if cnt >= 5 else "P2",
                "category": "coverage_gap",
                "intent": intent,
                "industry": ind,
                "keyword_fail_count": cnt,
                "fail_rate_in_corpus": rate,
                "action_zh": (
                    f"在知识库中补充「{intent}」×「{ind}」的独立话术/案例卡片，"
                    "或修正现有切片行业/意图元数据，使检索能稳定命中关键词。"
                ),
            }
        )

    for cid, cnt in top1_on_kw_fail.most_common(5):
        knowledge_actions.append(
            {
                "priority": "P0" if cnt >= 8 else "P1",
                "category": "dominant_chunk",
                "chunk_id": cid,
                "keyword_fail_top1_count": cnt,
                "action_zh": (
                    "该切片在大量失败用例中占据首位，可能过宽或与多意图重叠："
                    "考虑拆分、降权（元数据 priority）、或补充更垂直切片以分流。"
                ),
            }
        )

    if base_fail:
        n_b = len(base_fail)
        knowledge_actions.insert(
            0,
            {
                "priority": "P0",
                "category": "regression",
                "baseline_miss_count": n_b,
                "action_zh": (
                    f"共 {n_b} 条用例未召回生成基线时的切片，说明近期检索/索引与快照不一致。"
                    "请结合业务判断是否回归；若确为有意改版，应重新执行 generate_rag_cases --fill-baseline 刷新锚点。"
                    "禁止为「刷 baseline」用 LLM 批量编造切片；baseline 不是语义金标。"
                ),
            },
        )

    knowledge_actions = knowledge_actions[:max_actions]

    failure_samples = []
    for r in kw_fail[:max_samples]:
        tops = r.get("top_results") or []
        failure_samples.append(
            {
                "case_id": r.get("case_id"),
                "query": (r.get("query") or "")[:240],
                "industry": r.get("industry"),
                "intent_hint": r.get("intent_hint"),
                "top1_chunk_id": tops[0].get("chunk_id") if tops else None,
                "top1_preview": (tops[0].get("content_preview") if tops else "")[:120],
            }
        )

    bad_top1_chunks = [
        {"chunk_id": cid, "keyword_fail_top1_count": c} for cid, c in top1_on_kw_fail.most_common(15)
    ]

    bucket_kw = defaultdict(list)
    for r in rows:
        intent, ind = _intent_industry(r)
        bucket_kw[(intent, ind)].append(int(r.get("metrics", {}).get("keyword_hit@10", 0)))

    bucket_means = []
    for (intent, ind), vals in bucket_kw.items():
        if len(vals) < 5:
            continue
        bucket_means.append(
            {
                "intent": intent,
                "industry": ind,
                "cases": len(vals),
                "keyword_hit@10_mean": round(sum(vals) / len(vals), 4),
            }
        )
    bucket_means.sort(key=lambda x: x["keyword_hit@10_mean"])

    return {
        "cases_total": total,
        "keyword_fail_count": len(kw_fail),
        "baseline_miss_count": len(base_fail),
        "metrics_snapshot": metrics_snapshot or {},
        "methodology": {
            "llm_involved": False,
            "signal_sources": [
                "keyword_literal_overlap",
                "optional_retrieval_baseline_overlap",
                "aggregate_cooccurrence",
            ],
            "human_review_expected": True,
        },
        "bucket_keyword_hit10_tail": bucket_means[:10],
        "bad_top1_chunks": bad_top1_chunks,
        "knowledge_actions": knowledge_actions,
        "failure_samples": failure_samples,
        "loop_hints_zh": [
            "按 knowledge_actions 的 P0 项优先补文档或改元数据；每条建议上线前需人工核对事实与合规。",
            "在知识管理页上传/导入后，会写入 kb_eval_signal；由 kb_rag_eval_loop 重跑评测并对比 kb_rag_eval_last_metrics。",
            "知识库结构性优化后，可 regenerate 评测集（--fill-baseline）以更新回归锚点；勿为抬指标用 LLM 伪造切片。",
            "关键词命中为弱代理指标，不可替代小样本人工相关性评测。",
        ],
    }


def write_feedback_json(
    rows: list[dict[str, Any]],
    metrics_snapshot: dict[str, Any],
    path: Path,
    *,
    run_id: str,
) -> None:
    body = build_knowledge_feedback(rows, metrics_snapshot)
    body["run_id"] = run_id
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
