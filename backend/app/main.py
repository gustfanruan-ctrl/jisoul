# 文件路径：backend/app/main.py
# 用途：FastAPI 应用入口，注册路由 + 启动初始化（完整版，替换第 1 批的骨架）
# MVP 范围：完整入口

import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import settings
from app.knowledge.store import vector_store
from app.knowledge.embedder import preload_embedding_model
from app.knowledge.seed import seed_knowledge_base


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化资源"""
    start = time.time()
    logger.info(f"=== {settings.APP_NAME} {settings.APP_VERSION} 启动中 ===")

    # 创建必要目录
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)

    # 1. 预加载 Embedding 模型
    logger.info("Step 1/3: 预加载 Embedding 模型...")
    preload_embedding_model()

    # 2. 初始化向量数据库
    logger.info("Step 2/3: 初始化向量数据库...")
    vector_store.init()

    # 3. 灌入种子数据（仅首次）
    logger.info("Step 3/3: 检查种子数据...")
    seed_count = seed_knowledge_base()
    if seed_count > 0:
        logger.info(f"已灌入 {seed_count} 条种子数据")

    elapsed = round(time.time() - start, 1)
    logger.info(f"=== 启动完成，耗时 {elapsed}s，知识库 {vector_store.count()} 条 ===")

    yield

    logger.info("=== 应用关闭 ===")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ MVP 后需要限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "knowledge_count": vector_store.count(),
    }


# 注册路由
from app.api.routes_suggestion import router as suggestion_router
from app.api.routes_knowledge import router as knowledge_router

app.include_router(suggestion_router, prefix="/api/v1", tags=["建议生成"])
app.include_router(knowledge_router, prefix="/api/v1/knowledge", tags=["知识库管理"])