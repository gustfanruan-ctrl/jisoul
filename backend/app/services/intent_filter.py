# 文件路径：backend/app/services/intent_filter.py
# 用途：基于 LLM 返回的 intent 优化下次检索的 metadata 过滤
# MVP 范围：不增加额外 LLM 调用，而是利用已返回的 intent 结果
# 设计意图：LLM 已经在生成话术时识别 intent，我们缓存它用于后续检索优化

from typing import Optional, Dict, List
from collections import defaultdict
from loguru import logger

# 意图 → 卡片类型映射表
INTENT_TYPE_MAP = {
    "价格异议": ["sales_script", "combo_card", "lifecycle_card"],
    "预算不够": ["sales_script", "combo_card"],
    "竞品对比": ["product_card", "industry_deep_dive"],
    "功能咨询": ["product_card", "feature_highlight", "use_case"],
    "需求确认": ["lifecycle_card", "implementation_guide"],
    "实施难度": ["implementation_guide", "troubleshooting"],
    "技术问题": ["troubleshooting", "architecture_advice"],
    "客户成功": ["cs_card", "lifecycle_card"],
    "行业场景": ["industry_deep_dive", "industry_deep_scenario"],
    "产品介绍": ["product_intro", "product_card", "feature_highlight"],
}

# 意图关键词映射（用于规则引擎快速匹配）
INTENT_KEYWORD_MAP = {
    "价格异议": ["价格", "贵", "便宜", "预算", "花钱", "成本", "贵了", "太贵", "买不起"],
    "竞品对比": ["竞品", "对比", "比较", "他们", "别家", "其他产品", "永洪", "tableau", "powerbi"],
    "功能咨询": ["功能", "能做到", "支持", "有这个", "能实现", "特性"],
    "需求确认": ["需求", "想做个", "我们需要", "业务场景", "痛点", "问题"],
    "实施难度": ["实施", "部署", "上线", "多久", "周期", "难度", "复杂"],
    "技术问题": ["技术", "架构", "数据库", "集成", "接口", "对接"],
    "客户成功": ["客户成功", "续费", "留存", "流失", "活跃", "健康度"],
    "行业场景": ["行业", "场景", "案例", "同行", "我们行业", "制造业", "金融"],
}

# 意图缓存（session 级别）
_intent_cache: Dict[str, Dict] = defaultdict(dict)


class IntentFilterService:
    """意图过滤服务
    
    设计意图：
    - 不增加额外 LLM 调用
    - 利用 LLM 已返回的 intent 结果优化后续检索
    - 提供规则引擎快速匹配（作为 fallback）
    - 缓存意图结果用于 session 内多次检索
    """
    
    def get_intent_types(self, intent: str) -> List[str]:
        """根据意图返回应优先召回的卡片类型
        
        Args:
            intent: LLM 识别的意图（如"价格异议"）
            
        Returns:
            卡片类型列表（如 ["sales_script", "combo_card"]）
        """
        # 精确匹配
        if intent in INTENT_TYPE_MAP:
            return INTENT_TYPE_MAP[intent]
        
        # 模糊匹配（意图可能含额外描述）
        for key in INTENT_TYPE_MAP:
            if key in intent or intent in key:
                return INTENT_TYPE_MAP[key]
        
        # 未匹配则返回所有类型（不过滤）
        return []
    
    def quick_intent_by_keywords(self, query: str) -> Optional[str]:
        """关键词快速意图识别（不调 LLM）
        
        用于首次检索前的轻量意图判断
        
        Args:
            query: 用户查询文本
            
        Returns:
            意图字符串，未匹配返回 None
        """
        query_lower = query.lower()
        
        for intent, keywords in INTENT_KEYWORD_MAP.items():
            for kw in keywords:
                if kw in query_lower:
                    logger.debug(f"关键词匹配意图: '{kw}' → {intent}")
                    return intent
        
        return None
    
    def build_intent_filter(
        self,
        intent: Optional[str],
        industry: str = "通用",
    ) -> Optional[dict]:
        """构建基于意图的 metadata 过滤条件
        
        Args:
            intent: LLM 识别的意图（可选）
            industry: 行业
            
        Returns:
            ChromaDB where 过滤条件字典
        """
        filters = []
        
        # 行业过滤
        if industry and industry != "通用":
            filters.append({"$or": [{"industry": industry}, {"industry": "通用"}]})
        
        # 意图类型过滤
        if intent:
            target_types = self.get_intent_types(intent)
            if target_types:
                filters.append({"type": {"$in": target_types}})
        
        # 组合过滤条件
        if len(filters) == 0:
            return None
        elif len(filters) == 1:
            return filters[0]
        else:
            return {"$and": filters}
    
    def cache_intent(self, session_id: str, intent: str, entities: dict):
        """缓存 session 的意图结果
        
        用于后续检索时复用意图信息
        
        Args:
            session_id: 会话 ID
            intent: 意图
            entities: 提取的实体
        """
        _intent_cache[session_id]["intent"] = intent
        _intent_cache[session_id]["entities"] = entities
        _intent_cache[session_id]["timestamp"] = logger.info(f"缓存意图: session={session_id} intent={intent}")
    
    def get_cached_intent(self, session_id: str) -> Optional[str]:
        """获取缓存的意图"""
        return _intent_cache.get(session_id, {}).get("intent")
    
    def clear_cache(self, session_id: str):
        """清除 session 缓存"""
        if session_id in _intent_cache:
            del _intent_cache[session_id]


# 全局单例
intent_filter_service = IntentFilterService()