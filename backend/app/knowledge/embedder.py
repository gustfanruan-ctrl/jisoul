# 文件路径：backend/app/knowledge/embedder.py
# 用途：Embedding 模型加载与封装，适配 Chroma EmbeddingFunction 接口
# MVP 范围：bge-base-zh-v1.5 本地推理，启动预加载
# 变更：改用 sentence-transformers 替代 FlagEmbedding，解决 transformers 版本兼容问题

from typing import Optional
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
from loguru import logger

from app.config import settings

# 全局模型实例，启动时加载一次
_model = None


def _load_model():
    """加载 Embedding 模型到内存（首次调用约 10-15 秒）"""
    global _model
    if _model is not None:
        return _model

    logger.info(f"加载 Embedding 模型: {settings.EMBEDDING_MODEL_NAME} ...")
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(
            settings.EMBEDDING_MODEL_NAME,
            cache_folder=settings.EMBEDDING_MODEL_CACHE_DIR,
        )
        logger.info("Embedding 模型加载成功 (sentence-transformers)")
    except Exception as e:
        logger.error(f"Embedding 模型加载失败: {e}")
        raise
    return _model


def preload_embedding_model():
    """应用启动时调用，预加载模型"""
    _load_model()


class BGEEmbeddingFunction(EmbeddingFunction):
    """适配 Chroma 的 EmbeddingFunction 接口
    
    ChromaDB 要求实现 __call__(input: Documents) -> Embeddings
    Documents = list[str]
    Embeddings = list[list[float]]
    """

    def __call__(self, input: Documents) -> Embeddings:
        model = _load_model()
        # sentence-transformers 的 encode 返回 numpy array
        embeddings = model.encode(input, normalize_embeddings=True)
        return embeddings.tolist()


def get_embedding_function() -> BGEEmbeddingFunction:
    """获取 Chroma 兼容的 EmbeddingFunction 实例"""
    return BGEEmbeddingFunction()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """直接获取文本的 embedding 向量（用于非 Chroma 场景）"""
    model = _load_model()
    embeddings = model.encode(texts, normalize_embeddings=True)
    return embeddings.tolist()


def embed_query(text: str) -> list[float]:
    """单文本 embedding（便捷方法）"""
    return embed_texts([text])[0]