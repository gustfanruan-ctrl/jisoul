# 文件路径：backend/app/services/reranker.py
# 用途：Cross-Encoder Re-ranking 服务 - 精排优化检索结果
# MVP 范围：条件触发 + bge-reranker-base（轻量模型）
# 延迟控制：约 100-200ms（15条候选）

from typing import Optional
from loguru import logger
from sentence_transformers import CrossEncoder
from app.config import settings

# 全局模型实例，启动时预加载
_reranker_model: Optional[CrossEncoder] = None

def preload_reranker_model():
    """应用启动时调用，预加载 reranker 模型"""
    global _reranker_model
    if _reranker_model is not None:
        return
    
    logger.info(f"加载 Reranker 模型: {settings.RERANKER_MODEL_NAME} ...")
    try:
        _reranker_model = CrossEncoder(
            settings.RERANKER_MODEL_NAME,
            max_length=settings.RERANKER_MAX_LENGTH,
        )
        logger.info("Reranker 模型加载成功")
    except Exception as e:
        logger.warning(f"Reranker 模型加载失败: {e}，将禁用 rerank 功能")
        _reranker_model = None


class RerankerService:
    """Re-ranking 服务
    
    设计意图：
    - 条件触发：只在候选分散时才 rerank，避免每次都增加延迟
    - 轻量模型：使用 bge-reranker-base（约400MB），推理快
    - 延迟控制：15条候选约 100-150ms
    """
    
    def rerank(
        self,
        query: str,
        candidates: list[dict],
        top_k: int = 10,
    ) -> list[dict]:
        """对候选结果重新打分排序
        
        Args:
            query: 用户查询文本
            candidates: 粗排候选列表，每条含 content/score/metadata
            top_k: 返回条数
            
        Returns:
            重排后的候选列表（按 Cross-Encoder 分数降序）
        """
        if _reranker_model is None:
            logger.warning("Reranker 模型未加载，跳过 rerank")
            return candidates[:top_k]
        
        if not candidates:
            return candidates
        
        start_time = logger.info(f"开始 Re-ranking: {len(candidates)} 条候选")
        
        # 构建 (query, document) pairs
        pairs = [(query, c.get("content", "")) for c in candidates]
        
        try:
            # Cross-Encoder 打分
            scores = _reranker_model.predict(pairs)
            
            # 合并分数并排序
            scored_candidates = []
            for i, candidate in enumerate(candidates):
                candidate["rerank_score"] = float(scores[i])
                scored_candidates.append(candidate)
            
            # 按 rerank_score 降序
            scored_candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
            
            # 截断到 top_k
            result = scored_candidates[:top_k]
            
            # 记录日志
            if result:
                top1_rerank = result[0]["rerank_score"]
                top1_vector = result[0].get("score", 0)
                logger.info(
                    f"Re-ranking 完成: top1_rerank={top1_rerank:.4f} "
                    f"top1_vector={top1_vector:.4f} 返回 {len(result)} 条"
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Re-ranking 失败: {e}")
            return candidates[:top_k]
    
    def needs_rerank(self, results: list[dict]) -> bool:
        """判断是否需要触发 rerank
        
        条件：
        1. 候选数量 >= 5 条（太少没必要 rerank）
        2. Top 3 相似度差距 > 阈值（候选分散，需要精排）
        3. Top 1 相似度 < 阈值（不够确信，需要精排确认）
        
        Args:
            results: 粗排结果列表
            
        Returns:
            True 表示需要 rerank，False 表示直接返回粗排结果
        """
        if _reranker_model is None:
            return False
        
        if len(results) < settings.RERANK_MIN_CANDIDATES:
            return False
        
        # 提取 Top 3 相似度分数
        scores = [r.get("score", 0) for r in results[:3]]
        
        if len(scores) < 3:
            return False
        
        # 条件1：候选分散（Top3 相似度差距大）
        score_spread = max(scores) - min(scores)
        if score_spread > settings.RERANK_SCORE_SPREAD_THRESHOLD:
            logger.debug(f"触发 rerank: 候选分散 (spread={score_spread:.3f})")
            return True
        
        # 条件2：Top1 不够确信（相似度低于阈值）
        if scores[0] < settings.RERANK_LOW_CONFIDENCE_THRESHOLD:
            logger.debug(f"触发 rerank: Top1 不确信 (score={scores[0]:.3f})")
            return True
        
        return False


# 全局单例
reranker_service = RerankerService()