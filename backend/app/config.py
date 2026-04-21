# 文件路径：backend/app/config.py
# 用途：全局配置，支持环境变量覆盖
# MVP 范围：所有配置项集中管理
# v0.2.0 改动：新增 Reranker 配置 + Embedding 升级（最小改动，保留原配置）

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """机魂 MVP 全局配置"""
    
    # ============ 应用（保留原配置）============
    APP_NAME: str = "机魂 MVP"
    APP_VERSION: str = "0.2.0"  # v0.2.0 升级
    DEBUG: bool = True
    
    # ============ 服务端口（保留原配置）============
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # ============ LLM 默认配置（保留原配置）============
    DEFAULT_LLM_BASE_URL: str = "https://api.deepseek.com"
    DEFAULT_LLM_API_KEY: str = ""  # 必须配置，启动时检查
    DEFAULT_LLM_MODEL: str = "deepseek-chat"
    LLM_TIMEOUT_SECONDS: int = 100
    LLM_MAX_TOKENS: int = 1024
    LLM_TEMPERATURE: float = 0.3  # 话术生成偏确定性，不要太发散
    
    # ============ Embedding（v0.2.0 升级）============
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-large-zh-v1.5"  # v0.2.0: 从 base 升级到 large
    EMBEDDING_MODEL_CACHE_DIR: str = "./models/embedding"
    
    # ============ Re-ranking（v0.2.0 新增）============
    RERANKER_MODEL_NAME: str = "BAAI/bge-reranker-base"
    RERANKER_MAX_LENGTH: int = 512
    RERANK_MIN_CANDIDATES: int = 5
    RERANK_SCORE_SPREAD_THRESHOLD: float = 0.08
    RERANK_LOW_CONFIDENCE_THRESHOLD: float = 0.55
    RERANK_ENABLED: bool = True
    
    # ============ Chroma 向量数据库（保留原配置）============
    CHROMA_PERSIST_DIR: str = "./data/chroma"
    CHROMA_COLLECTION_NAME: str = "jisoul_knowledge"
    
    # ============ RAG 参数（v0.2.0 微调）============
    RAG_TOP_K: int = 15  # v0.2.0: 从 25 改为 15（减少 rerank 计算量）
    RAG_SIMILARITY_THRESHOLD: float = 0.35  # v0.2.0: 从 0.4 改为 0.35（粗排放宽）
    RAG_FINAL_K: int = 10  # v0.2.0 新增：最终返回条数
    
    # ============ 知识库（保留原配置）============
    UPLOAD_DIR: str = "./data/uploads"
    MAX_FILE_SIZE_MB: int = 10
    CHUNK_SIZE: int = 300
    CHUNK_OVERLAP: int = 50
    
    # ============ 上下文（保留原配置）============
    MAX_HISTORY_TURNS: int = 3
    
    # ============ 敏感词（保留原配置）============
    SENSITIVE_WORDS_PATH: str = "./data/sensitive_words.json"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()