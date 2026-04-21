# 文件路径：backend/app/services/rag_service.py
# 用途：RAG 检索服务 - 接收用户输入，从向量库检索相关知识切片
# MVP 范围：Top-K + 相似度阈值 + 行业 metadata 过滤 + 类型多样性保障
# v0.2.0 改动：集成条件触发 Re-ranking（最小改动，保留原逻辑）

import time
from collections import defaultdict
from typing import Optional
from loguru import logger
from app.config import settings
from app.knowledge.store import vector_store

# v0.2.0 新增：Reranker 服务
from app.services.reranker import reranker_service


# 知识切片类型枚举（保留原定义）
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

# 每种类型最多保留条数（保留原定义）
MAX_PER_TYPE = 5


class RAGService:
    """RAG 检索服务
    
    职责：
    1. 接收用户输入文本
    2. 构建 metadata 过滤条件（行业）
    3. 调用向量库检索 Top-K（粗排）
    4. v0.2.0 新增：条件触发 Re-ranking（精排）
    5. 类型多样性保障（每种 type 最多 MAX_PER_TYPE 条）
    6. 返回结构化检索结果
    """
    
    def search(
        self,
        query: str,
        industry: str = "通用",
        top_k: int = None,
        similarity_threshold: float = None,
        enable_rerank: bool = True,  # v0.2.0 新增参数
    ) -> list[dict]:
        """执行 RAG 检索（v0.2.0 新增 Re-ranking）
        
        Args:
            query: 用户输入的客户话语
            industry: 行业过滤，"通用"不过滤
            top_k: 返回条数，默认取配置
            similarity_threshold: 相似度阈值，默认取配置
            enable_rerank: 是否启用 rerank（v0.2.0 新增）
            
        Returns:
            检索结果列表，每条含：
            - chunk_id: str
            - content: str
            - score: float (0-1)
            - rerank_score: float (v0.2.0 新增，可选)
            - metadata: dict
        """
        if top_k is None:
            top_k = settings.RAG_TOP_K
        if similarity_threshold is None:
            similarity_threshold = settings.RAG_SIMILARITY_THRESHOLD
        
        start = time.time()
        
        # 构建 metadata 过滤条件（保留原逻辑）
        where_filter = None
        if industry and industry != "通用":
            where_filter = {
                "$or": [
                    {"industry": industry},
                    {"industry": "通用"},
                ]
            }
        
        # 调用向量库检索（保留原逻辑：请求更多条数以便后续去重）
        fetch_k = top_k * 2 if top_k < 40 else top_k
        
        raw_results = vector_store.search(
            query_text=query,
            top_k=fetch_k,
            similarity_threshold=similarity_threshold,
            where_filter=where_filter,
        )
        
        vector_ms = int((time.time() - start) * 1000)
        logger.info(
            f"向量检索(粗排): query='{query[:30]}...' industry={industry} "
            f"返回 {len(raw_results)} 条, 耗时 {vector_ms}ms"
        )
        
        if not raw_results:
            return []
        
        # v0.2.0 新增：条件触发 Re-ranking
        rerank_ms = 0
        if settings.RERANK_ENABLED and enable_rerank:
            if reranker_service.needs_rerank(raw_results):
                rerank_start = time.time()
                raw_results = reranker_service.rerank(
                    query=query,
                    candidates=raw_results,
                    top_k=min(fetch_k, len(raw_results)),
                )
                rerank_ms = int((time.time() - rerank_start) * 1000)
                logger.info(f"Re-ranking(精排): {len(raw_results)} 条, 耗时 {rerank_ms}ms")
        
        # 类型多样性保障（保留原逻辑）
        results = self._ensure_type_diversity(raw_results)
        
        # 截断到最终 top_k（保留原逻辑）
        results = results[:top_k]
        
        elapsed_ms = int((time.time() - start) * 1000)
        logger.info(
            f"RAG 检索完成: raw={len(raw_results)} → diversified={len(results)} 条 "
            f"向量耗时={vector_ms}ms rerank耗时={rerank_ms}ms 总耗时={elapsed_ms}ms"
        )
        
        return results
    
    def _ensure_type_diversity(self, results: list[dict]) -> list[dict]:
        """类型多样性保障：每种 type 最多保留 MAX_PER_TYPE 条
        
        v0.2.0 改动：按 rerank_score 或 score 排序
        """
        if not results:
            return results
        
        type_groups = defaultdict(list)
        for item in results:
            chunk_type = item.get("metadata", {}).get("type", "unknown")
            type_groups[chunk_type].append(item)
        
        diversified = []
        for chunk_type, group in type_groups.items():
            # v0.2.0 改动：优先按 rerank_score 排序
            group_sorted = sorted(
                group,
                key=lambda x: x.get("rerank_score", x.get("score", 0)),
                reverse=True
            )
            diversified.extend(group_sorted[:MAX_PER_TYPE])
        
        # v0.2.0 改动：优先按 rerank_score 排序
        diversified.sort(
            key=lambda x: x.get("rerank_score", x.get("score", 0)),
            reverse=True
        )
        
        return diversified


# 全局单例
rag_service = RAGService()