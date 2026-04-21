# 文件路径：backend/app/api/routes_knowledge.py
# 用途：知识库管理 API - 上传 / 切片列表 / 编辑 / 删除 / 检索测试
# MVP 范围：完整 CRUD + 检索测试

import os
import uuid
import time

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from loguru import logger

from app.config import settings
from app.knowledge.chunker import process_file
from app.knowledge.eval_signal import append_kb_eval_signal
from app.knowledge.store import vector_store
from app.models.schemas import (
    UploadResponse,
    ChunkListResponse,
    KnowledgeChunk,
    ChunkUpdateRequest,
    ChunkUpdateResponse,
    SearchTestRequest,
    SearchTestResponse,
    SearchTestResult,
    KnowledgeBatchImportItem,
    BatchImportRequest,
    BatchImportResponse,
)

router = APIRouter()

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {".txt", ".md", ".docx"}


@router.post("/upload", response_model=UploadResponse, summary="上传知识文档")
async def upload_document(file: UploadFile = File(...)):
    """上传文档 → 文本提取 → 切片 → Embedding → 存入向量库

    MVP 为同步处理，用户需等待 10-30 秒。
    """
    # 1. 校验文件
    file_name = file.filename or "unknown"
    ext = os.path.splitext(file_name)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}，仅支持 {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # 读取文件内容检查大小
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"文件大小 {size_mb:.1f}MB 超过限制 {settings.MAX_FILE_SIZE_MB}MB"
        )

    # 2. 保存临时文件
    file_id = f"file_{uuid.uuid4().hex[:12]}"
    save_dir = os.path.join(settings.UPLOAD_DIR, file_id)
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, file_name)

    with open(save_path, "wb") as f:
        f.write(content)

    logger.info(f"文件已保存: {save_path} ({size_mb:.1f}MB)")

    # 3. 文本提取 + 切片
    try:
        chunks = process_file(save_path, file_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"文件处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"文件处理失败: {e}")

    # 4. 构建切片数据并存入向量库
    chunk_ids = []
    documents = []
    metadatas = []
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    for i, chunk_text in enumerate(chunks):
        chunk_id = f"chunk_{uuid.uuid4().hex[:12]}"
        chunk_ids.append(chunk_id)
        documents.append(chunk_text)
        metadatas.append({
            "file_id": file_id,
            "file_name": file_name,
            "category": "未分类",
            "industry": "通用",
            "created_at": now,
            "chunk_index": i,
        })

    try:
        vector_store.add_chunks(ids=chunk_ids, documents=documents, metadatas=metadatas)
    except Exception as e:
        logger.error(f"向量化存储失败: {e}")
        raise HTTPException(status_code=500, detail=f"向量化存储失败: {e}")

    append_kb_eval_signal("chunks_added", source="upload", file_id=file_id, chunk_count=len(chunk_ids))
    logger.info(f"文件处理完成: {file_name} → {len(chunks)} 个切片")

    return UploadResponse(
        file_id=file_id,
        file_name=file_name,
        status="completed",
        chunk_count=len(chunks),
    )


@router.get("/chunks", response_model=ChunkListResponse, summary="查询切片列表")
async def list_chunks(
    file_id: str = Query(default=None, description="按文件 ID 筛选"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """查询知识库切片列表，支持按文件筛选和分页"""
    if file_id:
        raw_chunks = vector_store.get_chunks_by_file(file_id)
    else:
        raw_chunks = vector_store.get_all_chunks()

    # 按创建时间倒序排列
    raw_chunks.sort(
        key=lambda x: x.get("metadata", {}).get("created_at", ""),
        reverse=True,
    )

    total = len(raw_chunks)

    # 分页
    start = (page - 1) * page_size
    end = start + page_size
    page_chunks = raw_chunks[start:end]

    # 转换为响应格式
    chunks = []
    for item in page_chunks:
        meta = item.get("metadata", {})
        chunks.append(KnowledgeChunk(
            chunk_id=item["chunk_id"],
            content=item["content"],
            file_id=meta.get("file_id", ""),
            file_name=meta.get("file_name", ""),
            category=meta.get("category", "未分类"),
            industry=meta.get("industry", "通用"),
            created_at=meta.get("created_at", ""),
        ))

    return ChunkListResponse(total=total, chunks=chunks)


@router.put(
    "/chunks/{chunk_id}",
    response_model=ChunkUpdateResponse,
    summary="编辑切片文本",
)
async def update_chunk(chunk_id: str, req: ChunkUpdateRequest):
    """编辑切片纯文本，保存后自动重新 Embedding"""
    # 先查原数据
    existing = vector_store.get_chunk(chunk_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"切片不存在: {chunk_id}")

    # 保留原 metadata，更新 content
    metadata = existing.get("metadata", {})
    metadata["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    try:
        vector_store.update_chunk(
            chunk_id=chunk_id,
            document=req.content,
            metadata=metadata,
        )
    except Exception as e:
        logger.error(f"切片更新失败: {e}")
        raise HTTPException(status_code=500, detail=f"切片更新失败: {e}")

    append_kb_eval_signal("chunk_updated", source="api", chunk_id=chunk_id)
    return ChunkUpdateResponse(chunk_id=chunk_id, status="completed")


@router.delete("/chunks/{chunk_id}", summary="删除单条切片")
async def delete_chunk(chunk_id: str):
    """删除单条切片"""
    existing = vector_store.get_chunk(chunk_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"切片不存在: {chunk_id}")

    vector_store.delete_chunks(ids=[chunk_id])
    append_kb_eval_signal("chunk_deleted", source="api", chunk_id=chunk_id)
    return {"success": True}


@router.delete("/files/{file_id}", summary="删除整个文件（级联删除切片）")
async def delete_file(file_id: str):
    """按文件 ID 级联删除所有切片"""
    count = vector_store.delete_by_file_id(file_id)
    if count == 0:
        raise HTTPException(status_code=404, detail=f"文件不存在或无切片: {file_id}")

    # 同时删除上传的原始文件
    file_dir = os.path.join(settings.UPLOAD_DIR, file_id)
    if os.path.exists(file_dir):
        import shutil
        shutil.rmtree(file_dir, ignore_errors=True)

    append_kb_eval_signal("file_deleted", source="api", file_id=file_id, deleted_chunks=count)
    return {"success": True, "deleted_chunks": count}


@router.post("/search", response_model=SearchTestResponse, summary="检索测试")
async def search_test(req: SearchTestRequest):
    """知识库检索测试 - 输入文本，返回 Top-5 相关切片"""
    results = vector_store.search(
        query_text=req.query,
        top_k=5,
        similarity_threshold=0.0,  # 测试模式不过滤，全部返回
    )

    return SearchTestResponse(
        results=[
            SearchTestResult(
                chunk_id=r["chunk_id"],
                content=r["content"],
                score=round(r["score"], 4),
            )
            for r in results
        ]
    )

# ============================================================
# 批量导入结构化知识（JSON）
# ============================================================

def _card_to_chunk_content(item: KnowledgeBatchImportItem) -> str:
    """将不同类型的卡片统一转为可检索的纯文本"""

    if item.type == "product_card":
        parts = [
            f"【产品】{item.product}",
            f"【行业】{item.industry}",
            f"【行业痛点】{item.pain_points}",
        ]
        for i, uc in enumerate(item.use_cases, 1):
            scene = uc.get("scene", "") if isinstance(uc, dict) else ""
            desc = uc.get("description", "") if isinstance(uc, dict) else ""
            value = uc.get("value", "") if isinstance(uc, dict) else ""
            parts.append(f"【场景{i}】{scene}：{desc}（价值：{value}）")
        parts.append(f"【典型用户】{item.typical_users}")
        parts.append(f"【竞品对比】{item.competitor_comparison}")
        parts.append(f"【一句话推荐】{item.one_liner}")
        return "\n".join(parts)

    elif item.type == "combo_card":
        return "\n".join([
            f"【行业】{item.industry}",
            f"【客户需求】{item.scenario}",
            f"【推荐组合】{'＋'.join(item.recommended_combo)}",
            f"【方案说明】{item.combo_reason}",
            f"【落地路径】{item.implementation_outline}",
            f"【预期效果】{item.expected_value}",
            f"【客单价】{item.deal_size_hint}",
            f"【销售提醒】{item.sales_tip}",
        ])

    elif item.type == "industry_deep_dive":
        parts = [
            f"【行业深度画像】{item.industry}",
            f"【行业概述】{item.industry_overview}",
        ]
        org = item.org_structure
        if org:
            parts.append(f"【预算决策人】{org.get('budget_owner', '')}")
            parts.append(f"【最终用户】{org.get('end_users', '')}")
            parts.append(f"【决策链条】{org.get('decision_chain', '')}")
            parts.append(f"【内部推动者】{org.get('internal_champion', '')}")
        dl = item.data_landscape
        if dl:
            parts.append(f"【核心系统】{dl.get('core_systems', '')}")
            parts.append(f"【数据痛点】{dl.get('data_pain_points', '')}")
            parts.append(f"【数据成熟度】{dl.get('data_maturity', '')}")
            parts.append(f"【合规要求】{dl.get('compliance_requirements', '')}")
        fp = item.fanruan_penetration
        if fp:
            parts.append(f"【强势场景】{fp.get('strong_scenarios', '')}")
            parts.append(f"【薄弱场景】{fp.get('weak_scenarios', '')}")
            parts.append(f"【典型切入点】{fp.get('typical_entry_point', '')}")
            parts.append(f"【扩展路径】{fp.get('typical_expansion_path', '')}")
        cl = item.competitive_landscape
        if cl:
            for comp in cl.get("primary_competitors", []):
                if isinstance(comp, dict):
                    parts.append(
                        f"【竞品-{comp.get('name', '')}】"
                        f"优势：{comp.get('strength', '')}，"
                        f"劣势：{comp.get('weakness', '')}，"
                        f"帆软差异点：{comp.get('fanruan_differentiator', '')}"
                    )
            parts.append(f"【替代方案】{cl.get('alternative_approaches', '')}")
        bc = item.budget_cycle
        if bc:
            parts.append(f"【财年周期】{bc.get('fiscal_year', '')}")
            parts.append(f"【预算窗口】{bc.get('budget_planning_window', '')}")
            parts.append(f"【采购流程】{bc.get('procurement_process', '')}")
            parts.append(f"【典型单价】{bc.get('typical_deal_size', '')}")
        return "\n".join(parts)

    elif item.type in ("cs_card", "lifecycle_card"):
        parts = [
            f"【类型】深度知识-{item.cs_category or item.lifecycle_stage}",
            f"【行业】{item.industry}",
            f"【场景】{item.scenario}",
            f"【行业背景】{item.industry_context}",
        ]
        hs = item.health_signals
        if hs:
            if hs.get("positive"):
                parts.append(f"【健康信号】{'; '.join(hs['positive'])}")
            if hs.get("negative"):
                parts.append(f"【风险信号】{'; '.join(hs['negative'])}")
        ap = item.action_playbook
        if ap:
            parts.append(f"【触发条件】{ap.get('trigger', '')}")
            parts.append(f"【负责人】{ap.get('owner', '')}")
            for j, step in enumerate(ap.get("action_steps", []), 1):
                parts.append(f"【步骤{j}】{step}")
            parts.append(f"【时间窗口】{ap.get('timeline', '')}")
            parts.append(f"【成功标准】{ap.get('success_criteria', '')}")
            if ap.get("tools_needed"):
                parts.append(f"【所需工具】{ap['tools_needed']}")
        tt = item.talk_track
        if tt:
            if tt.get("to_business_user"):
                parts.append(f"【对业务用户】{tt['to_business_user']}")
            if tt.get("to_it_admin"):
                parts.append(f"【对IT管理员】{tt['to_it_admin']}")
            if tt.get("to_decision_maker"):
                parts.append(f"【对决策者】{tt['to_decision_maker']}")
        if item.expansion_hooks:
            parts.append(f"【增购机会】{item.expansion_hooks}")
        if item.risk_mitigation:
            parts.append(f"【风险与挽回】{item.risk_mitigation}")
        if item.reference_case:
            parts.append(f"【参考案例】{item.reference_case}")
        ism = item.industry_specific_metrics
        if ism and ism.get("metric_name"):
            parts.append(
                f"【行业指标】{ism['metric_name']}："
                f"{ism.get('how_product_impacts', '')}"
                f"（基准：{ism.get('benchmark', '')}）"
            )
        return "\n".join(parts)

    else:  # sales_script 或未知类型
        return item.content or ""


def _card_to_suggested_response(item: KnowledgeBatchImportItem) -> str:
    """提取建议话术"""
    if item.type == "product_card":
        return item.one_liner
    elif item.type == "combo_card":
        return item.sales_tip
    elif item.type in ("cs_card", "lifecycle_card"):
        tt = item.talk_track
        if tt:
            if tt.get("to_decision_maker"):
                return tt["to_decision_maker"]
            if tt.get("to_business_user"):
                return tt["to_business_user"]
        return item.expansion_hooks or ""
    elif item.type == "industry_deep_dive":
        fp = item.fanruan_penetration
        if fp and fp.get("typical_entry_point"):
            return fp["typical_entry_point"]
        return ""
    else:
        return item.suggested_response or ""


@router.post("/import", response_model=BatchImportResponse, summary="批量导入JSON知识库")
async def batch_import_knowledge(req: BatchImportRequest):
    """批量导入结构化知识卡片。
    支持类型：product_card、combo_card、sales_script、cs_card、lifecycle_card、industry_deep_dive。
    自动转为统一切片格式，向量化后存入 Chroma。
    """
    from datetime import datetime

    imported = 0
    errors = []

    batch_ids = []
    batch_documents = []
    batch_metadatas = []

    for i, item in enumerate(req.items):
        try:
            content = _card_to_chunk_content(item)
            if not content.strip():
                errors.append(f"第{i+1}条：content 为空，跳过")
                continue

            chunk_id = f"import_{item.type}_{uuid.uuid4().hex[:8]}"
            suggested = _card_to_suggested_response(item)

            metadata = {
                "file_id": f"batch_import_{item.type}",
                "file_name": f"batch_import_{item.type}",
                "type": item.type,
                "category": item.category or item.cs_category or item.lifecycle_stage or item.type,
                "industry": item.industry,
                "priority": str(item.priority),
                "card_id": item.card_id or "",
                "case_source": item.case_source or "",
                "trigger_scene": item.trigger_scene or item.scenario or "",
                "keywords": item.keywords,
                "suggested_response": suggested,
                "source_type": item.type,
                "created_at": datetime.now().isoformat(),
            }

            batch_ids.append(chunk_id)
            batch_documents.append(content)
            batch_metadatas.append(metadata)
            imported += 1

        except Exception as e:
            errors.append(f"第{i+1}条：{str(e)}")

    # 批量写入向量库
    if batch_ids:
        try:
            # Chroma 单次 add 有数量限制，分批写入
            BATCH_SIZE = 100
            for start in range(0, len(batch_ids), BATCH_SIZE):
                end = start + BATCH_SIZE
                vector_store.add_chunks(
                    ids=batch_ids[start:end],
                    documents=batch_documents[start:end],
                    metadatas=batch_metadatas[start:end],
                )
            logger.info(f"批量导入完成：{imported} 条写入向量库")
            append_kb_eval_signal("chunks_added", source="batch_import", imported=imported)
        except Exception as e:
            logger.error(f"向量库批量写入失败: {e}")
            return BatchImportResponse(
                total=len(req.items),
                imported=0,
                failed=len(req.items),
                errors=[f"向量库写入失败: {str(e)}"],
            )

    return BatchImportResponse(
        total=len(req.items),
        imported=imported,
        failed=len(req.items) - imported,
        errors=errors[:20],
    )
