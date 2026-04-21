# 文件路径：backend/app/api/routes_suggestion_enhanced.py
# 用途：核心链路 API - POST /api/v1/suggestions/enhanced
# MVP 范围：完整链路 = Metadata增强检索 → Prompt组装 → LLM调用 → 后处理
# 变更：新增增强版接口，支持 metadata 参数传入

import time
import uuid
from fastapi import APIRouter
from loguru import logger
from app.models.schemas import (
    SuggestRequest,
    SuggestResponse,
    Suggestion,
    FallbackReason,
)
from app.models.exceptions import VectorStoreError, VectorStoreTimeout
from app.config import settings
from app.services.metadata_enhanced_search import metadata_enhanced_search
from app.services.prompt_builder import prompt_builder
from app.services.llm_service import llm_service
from app.services.post_processor import post_processor

router = APIRouter()


@router.post("/suggestions/enhanced", response_model=SuggestResponse, summary="增强版建议话术")
async def get_suggestions_enhanced(req: SuggestRequest):
    """增强版核心链路：
    
    Metadata增强检索 → Prompt组装 → LLM生成 → 后处理 → 话术展示
    
    与基础版区别：
    1. 关键词匹配分数融合（利用 keywords 字段）
    2. 优先级加权（利用 priority 字段）
    3. 意图类型精准过滤（不再盲目"多样性保障")
    
    适用场景：
    - 行业化精准问题（如"制造业客户说预算不够，怎么说服他买FineBI?")
    - 需要高精度检索时
    """
    total_start = time.time()
    
    # ---- Step 1: Metadata 增强检索 ----
    rag_start = time.time()
    try:
        knowledge_chunks = metadata_enhanced_search.search(
            query=req.input_text,
            industry=req.industry,
            top_k=settings.RAG_FINAL_K,
            enable_keyword_match=True,
            enable_priority_weight=True,
            enable_intent_filter=True,
            enable_rerank=True,
        )
    except Exception as e:
        logger.error(f"Metadata增强检索失败: {e}")
        knowledge_chunks = []
    
    rag_ms = int((time.time() - rag_start) * 1000)
    logger.info(f"Metadata增强检索: {len(knowledge_chunks)} 条结果, 耗时 {rag_ms}ms")
    
    # 知识库为空标记
    no_knowledge = len(knowledge_chunks) == 0
    
    # ---- Step 2: 构建 Prompt ----
    system_prompt, user_prompt = prompt_builder.build(
        customer_input=req.input_text,
        knowledge_chunks=knowledge_chunks,
        industry=req.industry,
        style=req.style,
        history_inputs=req.history_inputs if req.history_inputs else None,
        session_summary=req.session_summary if req.session_summary else "",
    )
    
    # ---- Step 3: 调用 LLM ----
    llm_result = await llm_service.generate(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        llm_base_url=req.llm_base_url,
        llm_api_key=req.llm_api_key,
        llm_model=req.llm_model,
    )
    
    # ---- Step 4: 判断降级 ----
    if llm_result is None:
        logger.warning("LLM调用失败，触发降级")
        return _build_fallback_response(
            knowledge_chunks=knowledge_chunks,
            start_time=total_start,
            reason=FallbackReason.LLM_TIMEOUT,
        )
    
    # ---- Step 5: 后处理 ----
    raw_suggestions = llm_result.get("suggestions", [])
    if not raw_suggestions:
        logger.warning("LLM返回空建议")
        return _build_fallback_response(
            knowledge_chunks=knowledge_chunks,
            start_time=total_start,
            reason=FallbackReason.LLM_ERROR,
        )
    
    processed = post_processor.process(raw_suggestions)
    
    # ---- Step 6: 组装响应 ----
    suggestions = [
        Suggestion(
            id=f"sug_{uuid.uuid4().hex[:6]}",
            text=item["text"],
            source=item.get("source", "general"),
            ref_chunk_id=item.get("ref_chunk_id"),
        )
        for item in processed
    ]
    
    total_ms = int((time.time() - total_start) * 1000)
    
    # 记录意图信息
    intent = llm_result.get("intent", "未识别")
    entities = llm_result.get("entities", {})
    logger.info(
        f"增强建议生成完成: intent={intent} entities={entities} "
        f"suggestions={len(suggestions)} 总耗时={total_ms}ms"
    )
    
    return SuggestResponse(
        suggestions=suggestions,
        latency_ms=total_ms,
        fallback=False,
        fallback_reason=FallbackReason.NONE,
    )


def _build_fallback_response(
    knowledge_chunks: list[dict],
    start_time: float,
    reason: FallbackReason,
) -> SuggestResponse:
    """降级响应构建"""
    suggestions = []
    
    if knowledge_chunks:
        for i, chunk in enumerate(knowledge_chunks[:3]):
            content = chunk.get("content", "")
            if len(content) > 200:
                cut = content.rfind("。", 0, 200)
                content = content[:cut + 1] if cut > 50 else content[:200]
            suggestions.append(Suggestion(
                id=f"sug_fb_{uuid.uuid4().hex[:4]}",
                text=content,
                source="knowledge_base",
                ref_chunk_id=chunk.get("chunk_id"),
            ))
        suggestions.append(Suggestion(
            id=f"sug_fb_{uuid.uuid4().hex[:4]}",
            text="这个问题很好，我整理一下详细的资料，稍后发给您。",
            source="general",
            ref_chunk_id=None,
        ))
    else:
        suggestions = [
            Suggestion(
                id=f"sug_fb_{uuid.uuid4().hex[:4]}",
                text="这个点我帮您确认一下，回头给您详细的说明。",
                source="general",
                ref_chunk_id=None,
            ),
        ]
    
    total_ms = int((time.time() - start_time) * 1000)
    
    return SuggestResponse(
        suggestions=suggestions[:3],
        latency_ms=total_ms,
        fallback=True,
        fallback_reason=reason,
        message="AI响应较慢，已为您推荐知识库相关内容",
    )