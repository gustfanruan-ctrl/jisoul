# 文件路径：backend/app/knowledge/store.py
# 用途：Chroma 向量数据库操作封装，提供统一接口
# MVP 范围：完整 CRUD + 检索，接口抽象便于后续换 Qdrant
# ⚠️ MVP 后可能需要重构：Chroma 高并发性能有限，生产切 Qdrant
# 变更：search 方法异常分类处理（评审修复）

import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import Optional
from loguru import logger

from app.config import settings
from app.knowledge.embedder import get_embedding_function
from app.models.exceptions import VectorStoreError, VectorStoreTimeout


class VectorStore:
    """向量数据库操作封装层

    设计意图：
    - 对外暴露增删改查 + 检索接口
    - 内部绑定 Chroma，后续可替换实现
    - Embedding 由外部 EmbeddingFunction 注入
    """

    def __init__(self):
        self._client: Optional[chromadb.ClientAPI] = None
        self._collection: Optional[chromadb.Collection] = None

    def init(self):
        """初始化 Chroma 客户端和 Collection，应用启动时调用一次"""
        logger.info(f"初始化 Chroma，持久化路径: {settings.CHROMA_PERSIST_DIR}")
        self._client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        embedding_fn = get_embedding_function()
        self._collection = self._client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_NAME,
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},  # 余弦相似度
        )
        count = self._collection.count()
        logger.info(f"Chroma collection '{settings.CHROMA_COLLECTION_NAME}' 已就绪，当前 {count} 条记录")

    @property
    def collection(self) -> chromadb.Collection:
        if self._collection is None:
            raise VectorStoreError("VectorStore 未初始化，请先调用 init()")
        return self._collection

    # ============ 写操作 ============

    def add_chunks(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        """批量添加切片到向量库

        Args:
            ids: 切片 ID 列表
            documents: 切片文本列表（Chroma 会自动调用 embedding_function）
            metadatas: 元数据列表，每条含 file_id, file_name, category, industry, created_at
        """
        if not ids:
            return
        self.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )
        logger.info(f"向量库新增 {len(ids)} 条切片")

    def update_chunk(self, chunk_id: str, document: str, metadata: dict) -> None:
        """更新单条切片（编辑后重新 Embedding）"""
        self.collection.update(
            ids=[chunk_id],
            documents=[document],
            metadatas=[metadata],
        )
        logger.info(f"向量库更新切片: {chunk_id}")

    def delete_chunks(self, ids: list[str]) -> None:
        """批量删除切片"""
        if not ids:
            return
        self.collection.delete(ids=ids)
        logger.info(f"向量库删除 {len(ids)} 条切片")

    def delete_by_file_id(self, file_id: str) -> int:
        """按文件 ID 级联删除所有切片"""
        # 先查出该文件的所有切片 ID
        results = self.collection.get(
            where={"file_id": file_id},
            include=[],  # 只需要 IDs
        )
        ids = results["ids"]
        if ids:
            self.collection.delete(ids=ids)
            logger.info(f"按文件 {file_id} 删除 {len(ids)} 条切片")
        return len(ids)

    # ============ 检索（修复：异常分类） ============

    def search(
        self,
        query_text: str,
        top_k: int = 5,
        similarity_threshold: float = 0.5,
        where_filter: Optional[dict] = None,
    ) -> list[dict]:
        """向量检索（修复版：异常分类处理）

        Raises:
            VectorStoreError: Chroma 内部错误（连接失败、数据损坏等）
            VectorStoreTimeout: 检索超时（正常不应发生，Chroma 是本地调用）
        """
        query_params = {
            "query_texts": [query_text],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where_filter:
            query_params["where"] = where_filter

        try:
            results = self.collection.query(**query_params)
        except TimeoutError as e:
            logger.error(f"向量检索超时: {e}")
            raise VectorStoreTimeout(f"检索超时: {e}")
        except OSError as e:
            logger.error(f"向量库文件系统错误: {e}")
            raise VectorStoreError(f"知识库存储异常: {e}")
        except Exception as e:
            logger.error(f"向量检索失败 [{type(e).__name__}]: {e}")
            raise VectorStoreError(f"知识库检索异常: {e}")

        # Chroma cosine distance: distance = 1 - cosine_similarity
        # 所以 similarity = 1 - distance
        items = []
        if results and results["ids"] and results["ids"][0]:
            for i, chunk_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i]
                similarity = 1.0 - distance
                if similarity < similarity_threshold:
                    continue
                items.append({
                    "chunk_id": chunk_id,
                    "content": results["documents"][0][i],
                    "score": round(similarity, 4),
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                })

        logger.debug(f"检索 '{query_text[:30]}...' → {len(items)} 条结果（阈值 {similarity_threshold}）")
        return items

    # ============ 读操作 ============

    def get_chunk(self, chunk_id: str) -> Optional[dict]:
        """按 ID 获取单条切片"""
        results = self.collection.get(
            ids=[chunk_id],
            include=["documents", "metadatas"],
        )
        if results and results["ids"]:
            return {
                "chunk_id": results["ids"][0],
                "content": results["documents"][0],
                "metadata": results["metadatas"][0] if results["metadatas"] else {},
            }
        return None

    def get_chunks_by_file(self, file_id: str) -> list[dict]:
        """按文件 ID 获取所有切片"""
        results = self.collection.get(
            where={"file_id": file_id},
            include=["documents", "metadatas"],
        )
        items = []
        if results and results["ids"]:
            for i, chunk_id in enumerate(results["ids"]):
                items.append({
                    "chunk_id": chunk_id,
                    "content": results["documents"][i],
                    "metadata": results["metadatas"][i] if results["metadatas"] else {},
                })
        return items

    def get_all_chunks(self) -> list[dict]:
        """获取全部切片（MVP 规模小，直接全量拉取）
        ⚠️ MVP 后需要分页
        """
        results = self.collection.get(
            include=["documents", "metadatas"],
        )
        items = []
        if results and results["ids"]:
            for i, chunk_id in enumerate(results["ids"]):
                items.append({
                    "chunk_id": chunk_id,
                    "content": results["documents"][i],
                    "metadata": results["metadatas"][i] if results["metadatas"] else {},
                })
        return items

    def count(self) -> int:
        """当前切片总数"""
        return self.collection.count()


# 全局单例
vector_store = VectorStore()