"""知识库变更信号：驱动评测闭环（评测 → 改进知识库 → 再评测）。

仅追加 JSON 行，不触发 LLM；后续评测脚本也应保持无 LLM，以免指标与某一模型耦合。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def kb_eval_signal_path() -> Path:
    p = _backend_root() / "data" / "kb_eval_signal.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def append_kb_eval_signal(event: str, **extra: Any) -> None:
    """在向量库发生写操作后追加一行信号（供 kb_rag_eval_loop 消费）。"""
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **extra,
    }
    path = kb_eval_signal_path()
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError as e:
        logger.warning(f"kb_eval_signal write failed: {e}")


def kb_eval_signal_nonempty() -> bool:
    path = kb_eval_signal_path()
    if not path.exists():
        return False
    return bool(path.read_text(encoding="utf-8", errors="replace").strip())


def clear_kb_eval_signals() -> None:
    path = kb_eval_signal_path()
    if path.exists():
        path.write_text("", encoding="utf-8")
