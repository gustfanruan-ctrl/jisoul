# 文件路径：backend/app/services/metadata_enhanced_search.py
# 用途：Metadata 增强检索 - 充分利用 JSON 卡片的 keywords/priority/scenario 等字段
# MVP 范围：关键词匹配 + 优先级加权 + 场景匹配 + 意图类型精准过滤
# 设计意图：解决"行业化问题检索精度低"的问题，让 JSON 标签真正发挥作用

import time
import re
from typing import Optional, List, Dict
from collections import defaultdict
from loguru import logger
from app.config import settings
from app.knowledge.store import vector_store
from app.services.reranker import reranker_service

# 意图关键词映射表（用于快速意图识别）
INTENT_KEYWORD_MAP = {
    "价格异议": ["价格", "贵", "便宜", "预算", "花钱", "成本", "贵了", "太贵", "买不起", "没钱", "降价", "优惠"],
    "竞品对比": ["竞品", "对比", "比较", "他们", "别家", "其他产品", "永洪", "tableau", "powerbi", "smartbi", "优势", "区别"],
    "功能咨询": ["功能", "能做到", "支持", "有这个", "能实现", "特性", "有什么功能", "功能列表"],
    "需求确认": ["需求", "想做个", "我们需要", "业务场景", "痛点", "问题", "困难", "挑战"],
    "实施难度": ["实施", "部署", "上线", "多久", "周期", "难度", "复杂", "搞多久", "能上线"],
    "技术问题": ["技术", "架构", "数据库", "集成", "接口", "对接", "连接", "数据源"],
    "客户成功": ["客户成功", "续费", "留存", "流失", "活跃", "健康度", "使用情况"],
    "行业场景": ["行业", "场景", "案例", "同行", "我们行业", "制造业", "金融", "医疗", "零售"],
    "数据平台": ["数据平台", "数据打通", "数据整合", "数据分散", "数据孤岛", "统一数据"],
    "报表需求": ["报表", "看板", "驾驶舱", "可视化", "dashboard", "监控", "报表开发"],
}

# 意图 → 卡片类型精准映射
INTENT_TYPE_MAP = {
    "价格异议": ["sales_script", "combo_card"],
    "竞品对比": ["product_card", "industry_deep_dive"],
    "功能咨询": ["product_card", "feature_highlight", "use_case"],
    "需求确认": ["lifecycle_card", "implementation_guide"],
    "实施难度": ["implementation_guide", "troubleshooting"],
    "技术问题": ["troubleshooting", "architecture_advice"],
    "客户成功": ["cs_card", "lifecycle_card"],
    "行业场景": ["industry_deep_dive", "industry_deep_scenario"],
    "数据平台": ["combo_card", "implementation_guide"],
    "报表需求": ["lifecycle_card", "use_case"],
}


class MetadataEnhancedSearch:
    """Metadata 增强检索服务
    
    核心改进：
    1. 关键词提取 + 匹配增强（利用 keywords 字段）
    2. 优先级加权（利用 priority 字段）
    3. 场景关键词匹配（利用 scenario 字段）
    4. 意图类型精准过滤（解决"类型多样性反而稀释精准卡片"的问题）
    
    检索流程：
    1. 从用户 query 提取关键词
    2. 快速意图识别 → 确定目标卡片类型
    3. 构建 metadata 精准过滤条件
    4. 向量检索 + 关键词匹配分数融合
    5. Re-ranking 精排
    6. 优先级加权排序
    """
    
    def search(
        self,
        query: str,
        industry: str = "通用",
        top_k: int = 10,
        enable_keyword_match: bool = True,
        enable_priority_weight: bool = True,
        enable_intent_filter: bool = True,
        enable_rerank: bool = True,
    ) -> List[Dict]:
        """执行 Metadata 增强检索
        
        Args:
            query: 用户查询文本
            industry: 行业
            top_k: 返回条数
            enable_keyword_match: 是否启用关键词匹配增强
            enable_priority_weight: 是否启用优先级加权
            enable_intent_filter: 是否启用意图类型过滤
            enable_rerank: 是否启用 Re-ranking
            
        Returns:
            增强后的检索结果
        """
        start = time.time()
        
        # ---- Step 1: 关键词提取 ----
        query_keywords = self._extract_keywords(query)
        logger.info(f"查询关键词提取: '{query[:40]}...' → {query_keywords}")
        
        # ---- Step 2: 快速意图识别 ----
        intent = self._quick_intent(query)
        target_types = []
        if enable_intent_filter and intent:
            target_types = INTENT_TYPE_MAP.get(intent, [])
            logger.info(f"意图识别: '{intent}' → 目标类型: {target_types}")
        
        # ---- Step 3: 构建 metadata 精准过滤 ----
        where_filter = self._build_metadata_filter(
            industry=industry,
            target_types=target_types,
            query_keywords=query_keywords if enable_keyword_match else [],
        )
        
        # ---- Step 4: 向量检索（粗排） ----
        fetch_k = settings.RAG_TOP_K * 2  # 多拉一些候选，为后续融合做准备
        
        try:
            raw_results = vector_store.search(
                query_text=query,
                top_k=fetch_k,
                similarity_threshold=settings.RAG_SIMILARITY_THRESHOLD,
                where_filter=where_filter,
            )
        except Exception as e:
            logger.error(f"向量检索失败: {e}")
            raw_results = []
        
        vector_ms = int((time.time() - start) * 1000)
        logger.info(f"向量检索: {len(raw_results)} 条候选, 耗时 {vector_ms}ms")
        
        if not raw_results:
            return []
        
        # ---- Step 5: 关键词匹配分数融合 ----
        if enable_keyword_match:
            raw_results = self._fusion_keyword_scores(raw_results, query_keywords)
            logger.info(f"关键词匹配融合: Top3 keywords_score={raw_results[:3]}")
        
        # ---- Step 6: Re-ranking（精排） ----
        rerank_ms = 0
        if enable_rerank and reranker_service.needs_rerank(raw_results):
            rerank_start = time.time()
            raw_results = reranker_service.rerank(query, raw_results, top_k=min(20, len(raw_results)))
            rerank_ms = int((time.time() - rerank_start) * 1000)
        
        # ---- Step 7: 优先级加权 ----
        if enable_priority_weight:
            raw_results = self._apply_priority_weight(raw_results)
        
        # ---- Step 8: 最终融合排序 + 截断 ----
        results = self._final_sort(raw_results)
        results = results[:top_k]
        
        total_ms = int((time.time() - start) * 1000)
        logger.info(
            f"Metadata增强检索完成: intent={intent or '未识别'} "
            f"关键词={query_keywords} 结果={len(results)} "
            f"向量耗时={vector_ms}ms rerank耗时={rerank_ms}ms 总耗时={total_ms}ms"
        )
        
        return results
    
    def _extract_keywords(self, query: str) -> List[str]:
        """从查询文本提取关键词
        
        策略：
        1. 匹配 INTENT_KEYWORD_MAP 中的关键词
        2. 提取行业关键词（制造业、金融、医疗等）
        3. 提取产品关键词（FineBI、FineReport、简道云等）
        """
        keywords = []
        query_lower = query.lower()
        
        # 从意图关键词表匹配
        for intent_type, kw_list in INTENT_KEYWORD_MAP.items():
            for kw in kw_list:
                if kw in query_lower and kw not in keywords:
                    keywords.append(kw)
        
        # 行业关键词
        industry_keywords = [
            "制造业", "金融", "医疗", "建筑", "政府", "教育", 
            "物流", "电商", "互联网", "零售", "快消", "能源",
            "化工", "军工", "烟草", "畜牧", "农业", "银行",
        ]
        for kw in industry_keywords:
            if kw in query and kw not in keywords:
                keywords.append(kw)
        
        # 产品关键词
        product_keywords = [
            "finebi", "finereport", "fr", "bi", "简道云", "jdy",
            "finedatalink", "fdl", "帆软", "报表", "看板", "驾驶舱",
        ]
        for kw in product_keywords:
            if kw.lower() in query_lower and kw not in keywords:
                keywords.append(kw)
        
        return keywords
    
    def _quick_intent(self, query: str) -> Optional[str]:
        """快速意图识别（关键词匹配）"""
        query_lower = query.lower()
        
        # 按优先级匹配（价格异议最常见，优先检测）
        priority_order = ["价格异议", "竞品对比", "功能咨询", "需求确认", "实施难度", "技术问题", "客户成功", "行业场景", "数据平台", "报表需求"]
        
        for intent in priority_order:
            keywords = INTENT_KEYWORD_MAP.get(intent, [])
            for kw in keywords:
                if kw in query_lower:
                    return intent
        
        return None
    
    def _build_metadata_filter(
        self,
        industry: str,
        target_types: List[str],
        query_keywords: List[str],
    ) -> Optional[Dict]:
        """构建精准 metadata 过滤条件
        
        组合：
        1. 行业过滤（必须）
        2. 类型过滤（如果有意图识别）
        3. 关键词过滤（可选，利用 keywords 字段）
        """
        filters = []
        
        # 行业过滤
        if industry and industry != "通用":
            filters.append({"$or": [{"industry": industry}, {"industry": "通用"}]})
        
        # 类型精准过滤（不再做"多样性保障"，而是精准召回）
        if target_types:
            filters.append({"type": {"$in": target_types}})
        
        # 关键词过滤（放宽，用 OR 匹配任一关键词）
        # 注意：ChromaDB 的 where 过滤不支持复杂正则，这里用简单匹配
        if query_keywords and len(query_keywords) <= 3:  # 关键词太多会过度过滤
            keyword_filters = []
            for kw in query_keywords[:3]:
                # 尝试匹配 keywords 字段（元数据中的 keywords）
                keyword_filters.append({"keywords": {"$contains": kw}})
            if keyword_filters:
                filters.append({"$or": keyword_filters})
        
        # 组合
        if len(filters) == 0:
            return None
        elif len(filters) == 1:
            return filters[0]
        else:
            return {"$and": filters}
    
    def _fusion_keyword_scores(
        self,
        results: List[Dict],
        query_keywords: List[str],
    ) -> List[Dict]:
        """关键词匹配分数融合
        
        计算 keywords_match_score：
        - 卡片的 keywords 字段包含多少个查询关键词
        - 每匹配一个关键词 +0.1 分
        
        最终分数 = vector_score * 0.6 + keywords_score * 0.4
        """
        for item in results:
            card_keywords = item.get("metadata", {}).get("keywords", "")
            if isinstance(card_keywords, str):
                card_keywords_list = [k.strip() for k in card_keywords.split(",")]
            else:
                card_keywords_list = []
            
            # 计算匹配数
            match_count = 0
            for qk in query_keywords:
                for ck in card_keywords_list:
                    if qk.lower() in ck.lower() or ck.lower() in qk.lower():
                        match_count += 1
                        break
            
            # keywords_score = 匹配数 * 0.15（最多 0.6）
            keywords_score = min(match_count * 0.15, 0.6)
            item["keywords_score"] = keywords_score
            
            # 融合分数
            vector_score = item.get("score", 0.5)
            item["fusion_score"] = vector_score * 0.6 + keywords_score * 0.4
        
        # 按融合分数重排
        results.sort(key=lambda x: x.get("fusion_score", 0), reverse=True)
        
        return results
    
    def _apply_priority_weight(self, results: List[Dict]) -> List[Dict]:
        """优先级加权
        
        卡片的 priority 字段（1-10）加权：
        - priority >= 9: +0.15 分
        - priority >= 7: +0.10 分
        - priority >= 5: +0.05 分
        """
        for item in results:
            priority = item.get("metadata", {}).get("priority", 5)
            if isinstance(priority, (int, float)):
                if priority >= 9:
                    priority_bonus = 0.15
                elif priority >= 7:
                    priority_bonus = 0.10
                elif priority >= 5:
                    priority_bonus = 0.05
                else:
                    priority_bonus = 0
            else:
                priority_bonus = 0
            
            item["priority_bonus"] = priority_bonus
            
            # 最终分数融合
            base_score = item.get("fusion_score", item.get("rerank_score", item.get("score", 0.5)))
            item["final_score"] = base_score + priority_bonus
        
        return results
    
    def _final_sort(self, results: List[Dict]) -> List[Dict]:
        """最终排序：综合 rerank_score + keywords_score + priority_bonus"""
        def get_sort_score(item):
            # 优先用 rerank_score，其次 fusion_score，再次 vector_score
            base = item.get("rerank_score", item.get("fusion_score", item.get("score", 0.5)))
            priority_bonus = item.get("priority_bonus", 0)
            return base + priority_bonus
        
        results.sort(key=get_sort_score, reverse=True)
        return results


# 全局单例
metadata_enhanced_search = MetadataEnhancedSearch()