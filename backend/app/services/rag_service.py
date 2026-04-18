# 文件路径：backend/app/services/rag_service.py
# 用途：RAG 检索服务 - 接收用户输入，从向量库检索相关知识切片
# MVP 范围：Top-K + 相似度阈值 + 行业 metadata 过滤 + 类型多样性保障

import time
from collections import defaultdict
from typing import Optional
from loguru import logger

from app.config import settings
from app.knowledge.store import vector_store


# 知识切片类型枚举
CHUNK_TYPES = [
    "product_card",
    "combo_card",
    "sales_script",
    "lifecycle_card",
    "industry_deep_dive",
    "cs_card",
    "troubleshooting",
    "implementation_guide",
    "architecture_advice",
    "industry_deep_scenario",
    "industry_trend",
    "industry_benchmark",
    "industry_regulation",
    "feature_highlight",
    "use_case",
    "product_intro",
]

# 每种类型最多保留条数
MAX_PER_TYPE = 5



class RAGService:
    """RAG 检索服务

    职责：
    1. 接收用户输入文本
    2. 构建 metadata 过滤条件（行业）
    3. 调用向量库检索 Top-K
    4. 类型多样性保障（每种 type 最多 MAX_PER_TYPE 条）
    5. 返回结构化检索结果
    """

    def search(
        self,
        query: str,
        industry: str = "通用",
        top_k: int = None,
        similarity_threshold: float = None,
    ) -> list[dict]:
        """执行 RAG 检索

        Args:
            query: 用户输入的客户话语
            industry: 行业过滤，"通用"不过滤
            top_k: 返回条数，默认取配置
            similarity_threshold: 相似度阈值，默认取配置

        Returns:
            检索结果列表，每条含：
            - chunk_id: str
            - content: str
            - score: float (0-1)
            - metadata: dict
        """
        if top_k is None:
            top_k = settings.RAG_TOP_K
        if similarity_threshold is None:
            similarity_threshold = settings.RAG_SIMILARITY_THRESHOLD

        start = time.time()

        # 构建 metadata 过滤条件
        where_filter = None
        if industry and industry != "通用":
            # 检索该行业 + 通用的知识
            where_filter = {
                "$or": [
                    {"industry": industry},
                    {"industry": "通用"},
                ]
            }

        # 调用向量库检索（请求更多条数以便后续去重）
        # 由于需要类型多样性保障，实际请求条数 = top_k * 2（确保有足够候选）
        fetch_k = top_k * 2 if top_k < 40 else top_k


        raw_results = vector_store.search(
            query_text=query,
            top_k=fetch_k,
            similarity_threshold=similarity_threshold,
            where_filter=where_filter,
        )

        # 类型多样性保障：每种 type 最多保留 MAX_PER_TYPE 条
        results = self._ensure_type_diversity(raw_results)

        # 截断到最终 top_k
        results = results[:top_k]

        elapsed_ms = int((time.time() - start) * 1000)
        logger.info(
            f"RAG 检索完成: query='{query[:30]}...' industry={industry} "
            f"raw={len(raw_results)} → diversified={len(results)} 条结果, 耗时 {elapsed_ms}ms"
        )

        return results

    def _ensure_type_diversity(self, results: list[dict]) -> list[dict]:
        """类型多样性保障：每种 type 最多保留 MAX_PER_TYPE 条"""
        if not results:
            return results

        type_groups = defaultdict(list)
        for item in results:
            chunk_type = item.get("metadata", {}).get("type", "unknown")
            type_groups[chunk_type].append(item)

        diversified = []
        for chunk_type, group in type_groups.items():
            group_sorted = sorted(group, key=lambda x: x.get("score", 0), reverse=True)
            diversified.extend(group_sorted[:MAX_PER_TYPE])

        diversified.sort(key=lambda x: x.get("score", 0), reverse=True)

        return diversified


# 全局单例
rag_service = RAGService()