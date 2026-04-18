# 文件路径：backend/app/services/post_processor.py
# 用途：LLM 输出后处理 - 高危词替换 + 格式清洗 + 相似去重
# MVP 范围：完整后处理链路

import json
import os
import re
import time
from typing import Optional
from loguru import logger

from app.config import settings


class PostProcessor:
    """后处理器

    处理链路：
    1. 高危词拦截与替换
    2. 格式清洗（去除多余空白、特殊字符）
    3. 相似去重（基于简单的字符重叠度，阈值 0.85）
    4. 长度校验（单条 ≤ 200 字）
    """

    def __init__(self):
        self._sensitive_words: list[str] = []
        self._replacement: str = "建议咨询专业团队"
        self._last_loaded: float = 0
        self._load_interval: int = 60  # 每 60 秒检查一次词表更新

    def _load_sensitive_words(self) -> None:
        """加载敏感词表（支持热更新）"""
        now = time.time()
        if now - self._last_loaded < self._load_interval and self._sensitive_words:
            return  # 未到刷新间隔

        path = settings.SENSITIVE_WORDS_PATH
        if not os.path.exists(path):
            logger.warning(f"敏感词表不存在: {path}")
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._sensitive_words = data.get("words", [])
            self._replacement = data.get("replacement", "建议咨询专业团队")
            self._last_loaded = now
            logger.debug(f"敏感词表已加载: {len(self._sensitive_words)} 个词")
        except Exception as e:
            logger.error(f"敏感词表加载失败: {e}")

    def process(self, suggestions: list[dict]) -> list[dict]:
        """执行完整后处理链路

        Args:
            suggestions: LLM 输出的建议列表，每条含 text / ref_chunk_id / source

        Returns:
            处理后的建议列表
        """
        if not suggestions:
            return []

        self._load_sensitive_words()

        processed = []
        for item in suggestions:
            text = item.get("text", "")
            if not text.strip():
                continue

            # Step 1: 格式清洗
            text = self._clean_format(text)

            # Step 2: 高危词替换
            text, was_replaced = self._replace_sensitive_words(text)

            # Step 3: 长度截断
            if len(text) > 200:
                # 在最后一个句号/问号处截断
                cut_pos = max(
                    text.rfind("。", 0, 200),
                    text.rfind("？", 0, 200),
                    text.rfind("！", 0, 200),
                    text.rfind(".", 0, 200),
                )
                if cut_pos > 50:  # 截断位置不能太靠前
                    text = text[:cut_pos + 1]
                else:
                    text = text[:200]

            processed.append({
                "text": text,
                "ref_chunk_id": item.get("ref_chunk_id"),
                "source": item.get("source", "general"),
            })

        # Step 4: 相似去重
        processed = self._deduplicate(processed, threshold=0.85)

        logger.debug(f"后处理完成: 输入 {len(suggestions)} 条 → 输出 {len(processed)} 条")
        return processed

    def _clean_format(self, text: str) -> str:
        """格式清洗"""
        # 去除首尾空白
        text = text.strip()
        # 去除连续空格
        text = re.sub(r' {2,}', ' ', text)
        # 去除连续换行
        text = re.sub(r'\n{2,}', '\n', text)
        # 去除序号前缀（LLM 可能输出 "1. " "- " 等）
        text = re.sub(r'^[\d]+[.、)）]\s*', '', text)
        text = re.sub(r'^[-•·]\s*', '', text)
        # 去除引号包裹（LLM 可能用引号包裹整条建议）
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]
        if text.startswith("「") and text.endswith("」"):
            text = text[1:-1]
        return text.strip()

    def _replace_sensitive_words(self, text: str) -> tuple[str, bool]:
        """高危词替换

        Returns:
            (处理后文本, 是否发生了替换)
        """
        was_replaced = False
        for word in self._sensitive_words:
            if word in text:
                text = text.replace(word, self._replacement)
                was_replaced = True
                logger.warning(f"高危词命中: '{word}'")
        return text, was_replaced

    def _deduplicate(self, suggestions: list[dict], threshold: float = 0.85) -> list[dict]:
        """相似去重（基于字符级 Jaccard 相似度）

        ⚠️ MVP 后可能需要重构：改用语义相似度去重
        """
        if len(suggestions) <= 1:
            return suggestions

        result = [suggestions[0]]
        for candidate in suggestions[1:]:
            is_duplicate = False
            for existing in result:
                sim = self._char_similarity(candidate["text"], existing["text"])
                if sim >= threshold:
                    is_duplicate = True
                    logger.debug(
                        f"相似去重: '{candidate['text'][:30]}...' "
                        f"与 '{existing['text'][:30]}...' 相似度 {sim:.2f}"
                    )
                    break
            if not is_duplicate:
                result.append(candidate)

        return result

    def _char_similarity(self, a: str, b: str) -> float:
        """字符级 Jaccard 相似度"""
        if not a or not b:
            return 0.0
        set_a = set(a)
        set_b = set(b)
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0


# 全局单例
post_processor = PostProcessor()