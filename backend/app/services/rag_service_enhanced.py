# 文件路径：backend/app/services/rag_service_enhanced.py
# 用途：RAG 检索增强版 - 带意图过滤 + Re-ranking
# MVP 范围：可选使用，用于高精度场景
# 设计：结合意图过滤 + 向量检索 + Re-ranking + 类型多样性

import time
from collections import defaultdict
from typing import Optional
from loguru import logger
from app.config import settings
from app.knowledge.store import vector_store
from app.services.reranker import reranker_service
from app.services.intent_filter import intent_filter_service

MAX_PER_TYPE = 3


class RAGServiceEnhanced:
    """RAG 检索增强版
    
    与基础版区别：
    1. 支持关键词快速意图识别（不调 LLM）
    2. 意图驱动的 metadata 精过滤
    3. 可选使用（前端可通过参数选择）
    
    适用场景：
    - 用户明确表达意图时（如"价格太贵怎么办"）
    - 需要高精度检索时
    """
    
    def search(
        self,
        query: str,
        industry: str = "通用",
        top_k: int = None,
        similarity_threshold: float = None,
        enable_rerank: bool = True,
        enable_intent_filter: bool = True,
        session_id: Optional[str] = None,
    ) -> list[dict]:
        """执行增强版 RAG 检索
        
        Args:
            query: 用户查询
            industry: 行业
            top_k: 返回条数
            similarity_threshold: 相似度阈值
            enable_rerank: 是否启用 rerank
            enable_intent_filter: 是否启用意图过滤
            session_id: 会话 ID（用于缓存意图）
            
        Returns:
            检索结果
        """
        if top_k is None:
            top_k = settings.RAG_FINAL_K
        if similarity_threshold is None:
            similarity_threshold = settings.RAG_SIMILARITY_THRESHOLD
        
        start = time.time()
        
        # ---- Step 1: 快速意图识别（关键词匹配） ----
        intent = None
        if enable_intent_filter:
            # 先尝试关键词快速匹配
            intent = intent_filter_service.quick_intent_by_keywords(query)
            
            # 如果有缓存意图，也考虑（后续可结合）
            cached_intent = intent_filter_service.get_cached_intent(session_id or "")
            if cached_intent and not intent:
                intent = cached_intent
            
            if intent:
                logger.info(f"快速意图识别: '{query[:30]}...' → {intent}")
        
        # ---- Step 2: 构建意图过滤条件 ----
        where_filter = intent_filter_service.build_intent_filter(intent, industry)
        
        if where_filter:
            logger.debug(f"意图过滤条件: {where_filter}")
        
        # ---- Step 3: 向量检索（粗排） ----
        fetch_k = settings.RAG_TOP_K
        
        try:
            raw_results = vector_store.search(
                query_text=query,
                top_k=fetch_k,
                similarity_threshold=similarity_threshold,
                where_filter=where_filter,
            )
        except Exception as e:
            logger.error(f"向量检索失败: {e}")
            raw_results = []
        
        vector_ms = int((time.time() - start) * 1000)
        
        # 如果意图过滤后结果太少，放宽条件重新检索
        if enable_intent_filter and len(raw_results) < 3 and where_filter:
            logger.warning(f"意图过滤结果过少({len(raw_results)}条)，放宽条件重新检索")
            raw_results = vector_store.search(
                query_text=query,
                top_k=fetch_k,
                similarity_threshold=similarity_threshold,
                where_filter={"$or": [{"industry": industry}, {"industry": "通用"}]},
            )
        
        logger.info(f"向量检索: {len(raw_results)} 条, 耗时 {vector_ms}ms")
        
        if not raw_results:
            return []
        
        # ---- Step 4: Re-ranking（精排） ----
        rerank_ms = 0
        if settings.RERANK_ENABLED and enable_rerank:
            if reranker_service.needs_rerank(raw_results):
                rerank_start = time.time()
                raw_results = reranker_service.rerank(query, raw_results, top_k=fetch_k)
                rerank_ms = int((time.time() - rerank_start) * 1000)
        
        # ---- Step 5: 类型多样性 ----
        results = self._ensure_type_diversity(raw_results)
        results = results[:top_k]
        
        total_ms = int((time.time() - start) * 1000)
        logger.info(
            f"增强检索完成: intent={intent or '未识别'} "
            f"结果={len(results)} 向量耗时={vector_ms}ms rerank耗时={rerank_ms}ms"
        )
        
        return results
    
    def _ensure_type_diversity(self, results: list[dict]) -> list[dict]:
        if not results:
            return results
        
        type_groups = defaultdict(list)
        for item in results:
            chunk_type = item.get("metadata", {}).get("type", "unknown")
            type_groups[chunk_type].append(item)
        
        diversified = []
        for chunk_type, group in type_groups.items():
            group_sorted = sorted(
                group,
                key=lambda x: x.get("rerank_score", x.get("score", 0)),
                reverse=True
            )
            diversified.extend(group_sorted[:MAX_PER_TYPE])
        
        diversified.sort(
            key=lambda x: x.get("rerank_score", x.get("score", 0)),
            reverse=True
        )
        
        return diversified


# 全局单例
rag_service_enhanced = RAGServiceEnhanced()