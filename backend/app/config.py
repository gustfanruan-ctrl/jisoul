# 文件路径：backend/app/config.py
# 用途：全局配置，支持环境变量覆盖
# MVP 范围：所有配置项集中管理

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """机魂 MVP 全局配置"""

    # ============ 应用 ============
    APP_NAME: str = "机魂 MVP"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # ============ 服务端口 ============
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ============ LLM 默认配置（用户可通过前端覆盖） ============
    DEFAULT_LLM_BASE_URL: str = "https://api.deepseek.com"
    DEFAULT_LLM_API_KEY: str = ""  # 必须配置，启动时检查
    DEFAULT_LLM_MODEL: str = "deepseek-chat"
    LLM_TIMEOUT_SECONDS: int = 100
    LLM_MAX_TOKENS: int = 1024
    LLM_TEMPERATURE: float = 0.3  # 话术生成偏确定性，不要太发散

    # ============ Embedding ============
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-base-zh-v1.5"
    # 模型缓存路径，避免每次下载
    EMBEDDING_MODEL_CACHE_DIR: str = "./models/embedding"

    # ============ Chroma 向量数据库 ============
    CHROMA_PERSIST_DIR: str = "./data/chroma"
    CHROMA_COLLECTION_NAME: str = "jisoul_knowledge"

    # ============ RAG 参数 ============
    RAG_TOP_K: int = 25
    RAG_SIMILARITY_THRESHOLD: float = 0.4

    # ============ 知识库 ============
    UPLOAD_DIR: str = "./data/uploads"
    MAX_FILE_SIZE_MB: int = 10
    CHUNK_SIZE: int = 300  # 默认切片长度（字符数）
    CHUNK_OVERLAP: int = 50  # 切片重叠

    # ============ 上下文 ============
    MAX_HISTORY_TURNS: int = 3

    # ============ 敏感词 ============
    SENSITIVE_WORDS_PATH: str = "./data/sensitive_words.json"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()