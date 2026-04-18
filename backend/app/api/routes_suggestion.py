# 文件路径：backend/app/api/routes_suggestion.py
# 用途：核心链路 API - POST /api/v1/suggestions
# MVP 范围：完整链路 = RAG 检索 → Prompt 组装 → LLM 调用 → 后处理 → 降级
# 变更：异常分类处理 + 友好错误信息（评审修复）

import time
import uuid

from fastapi import APIRouter
from loguru import logger

from app.models.schemas import (
    SuggestRequest,
    SuggestResponse,
    Suggestion,
    FallbackReason,
    SummaryRequest,
    SummaryResponse,
)
from app.models.exceptions import VectorStoreError, VectorStoreTimeout
from app.services.rag_service import rag_service
from app.services.prompt_builder import prompt_builder
from app.services.llm_service import llm_service
from app.services.post_processor import post_processor

router = APIRouter()


@router.post("/suggestions", response_model=SuggestResponse, summary="获取建议话术")
async def get_suggestions(req: SuggestRequest):
    """核心链路：文本输入 → 知识检索 → LLM 生成 → 后处理 → 话术展示

    降级策略：
    - LLM 正常返回 → 展示生成话术
    - LLM 超时/错误 → 展示 RAG 原始知识片段 + 模板转向话术
    - 知识库无结果 → LLM 基于通用知识生成，标注 source=general
    """
    total_start = time.time()

    # ---- Step 1: RAG 检索 ----
    rag_start = time.time()
    knowledge_chunks = []
    rag_error = False

    try:
        knowledge_chunks = rag_service.search(
            query=req.input_text,
            industry=req.industry,
        )
    except VectorStoreTimeout as e:
        logger.warning(f"RAG 检索超时: {e.message}")
        rag_error = True
    except VectorStoreError as e:
        logger.error(f"RAG 检索服务异常: {e.message}")
        rag_error = True
    except Exception as e:
        logger.error(f"RAG 检索未知异常: {type(e).__name__}: {e}")
        rag_error = True

    rag_ms = int((time.time() - rag_start) * 1000)
    logger.info(f"RAG 检索: {len(knowledge_chunks)} 条结果, 耗时 {rag_ms}ms, 异常={rag_error}")

    # 知识库为空的特殊标记
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

    # ---- Step 4: 判断是否需要降级 ----
    if llm_result is None:
        # LLM 超时或错误 → 降级
        logger.warning("LLM 调用失败，触发降级策略")
        return _build_fallback_response(
            knowledge_chunks=knowledge_chunks,
            start_time=total_start,
            reason=FallbackReason.LLM_TIMEOUT if not rag_error else FallbackReason.LLM_ERROR,
        )

    # ---- Step 5: 后处理 ----
    raw_suggestions = llm_result.get("suggestions", [])

    if not raw_suggestions:
        # LLM 返回了但没有建议 → 也降级
        logger.warning("LLM 返回空建议列表，触发降级")
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

    # 写日志（intent / entities 不返回前端，但记录到日志）
    intent = llm_result.get("intent", "未识别")
    entities = llm_result.get("entities", {})
    logger.info(
        f"建议生成完成: intent={intent} entities={entities} "
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
    """构建降级响应

    策略：
    - 如果有 RAG 结果 → 取前 3 条知识片段原文作为建议
    - 如果无 RAG 结果 → 返回通用转向话术
    """
    suggestions = []

    if knowledge_chunks:
        # 用 RAG 原始片段 + 模板话术
        for i, chunk in enumerate(knowledge_chunks[:3]):
            content = chunk.get("content", "")
            # 截断到 200 字
            if len(content) > 200:
                cut = content.rfind("。", 0, 200)
                content = content[:cut + 1] if cut > 50 else content[:200]

            suggestions.append(Suggestion(
                id=f"sug_fb_{uuid.uuid4().hex[:4]}",
                text=content,
                source="knowledge_base",
                ref_chunk_id=chunk.get("chunk_id"),
            ))

        # 追加一条转向话术
        suggestions.append(Suggestion(
            id=f"sug_fb_{uuid.uuid4().hex[:4]}",
            text="这个问题很好，我整理一下详细的资料，稍后发给您。",
            source="general",
            ref_chunk_id=None,
        ))
    else:
        # 完全无知识 → 通用话术
        suggestions = [
            Suggestion(
                id=f"sug_fb_{uuid.uuid4().hex[:4]}",
                text="这个点我帮您确认一下，回头给您详细的说明。",
                source="general",
                ref_chunk_id=None,
            ),
            Suggestion(
                id=f"sug_fb_{uuid.uuid4().hex[:4]}",
                text="您提的这个场景很有代表性，我跟产品团队确认一下最新的方案，尽快反馈给您。",
                source="general",
                ref_chunk_id=None,
            ),
        ]

    total_ms = int((time.time() - start_time) * 1000)

    # 根据降级原因返回友好提示
    friendly_messages = {
        FallbackReason.LLM_TIMEOUT: "AI 响应较慢，已为您推荐知识库相关内容",
        FallbackReason.LLM_ERROR: "AI 服务暂时不可用，已为您推荐知识库相关内容",
        FallbackReason.NO_KNOWLEDGE: "未找到相关知识，建议补充知识库",
    }

    return SuggestResponse(
        suggestions=suggestions[:3],  # 最多 3 条
        latency_ms=total_ms,
        fallback=True,
        fallback_reason=reason,
        message=friendly_messages.get(reason, ""),
    )


# ============ 会议摘要生成接口 ============

@router.post("/summary", response_model=SummaryResponse, summary="生成会议摘要")
async def generate_summary(req: SummaryRequest):
    """将多轮对话压缩为 ≤150 字的结构化摘要。
    
    前端每累积 5 轮新对话时调用一次。
    """
    import time
    start = time.time()

    system_prompt = """你是一个B2B销售会议的摘要助手。请将以下多轮对话压缩为一段≤150字的结构化摘要。
必须包含以下要素（如果对话中提及）：
- 客户行业和公司规模
- 客户预算或价格敏感度
- 客户核心需求和关注点
- 客户已明确拒绝或不感兴趣的内容
- 当前对话进展到哪个阶段（初步了解/需求确认/方案讨论/价格谈判/异议处理）

如果某个要素对话中未提及，直接跳过，不要编造。
输出纯文本，不要用 markdown 格式。"""

    user_content = "以下是对话历史：\n\n"
    for i, text in enumerate(req.inputs, 1):
        user_content += f"第{i}轮：{text}\n"

    if req.existing_summary:
        user_content += f"\n之前的摘要：{req.existing_summary}\n"
        user_content += "\n请将之前的摘要和新对话合并，输出更新后的完整摘要。"

    try:
        result = await llm_service.generate_raw(
            system_prompt=system_prompt,
            user_prompt=user_content,
            llm_base_url=req.llm_base_url,
            llm_api_key=req.llm_api_key,
            llm_model=req.llm_model,
        )
        summary_text = result.strip() if result else ""
        # 强制截断到 200 字，留一些余量
        if len(summary_text) > 200:
            summary_text = summary_text[:200]
    except Exception as e:
        logger.warning(f"摘要生成失败: {e}")
        summary_text = ""

    latency_ms = int((time.time() - start) * 1000)

    return SummaryResponse(
        summary=summary_text,
        latency_ms=latency_ms
    )