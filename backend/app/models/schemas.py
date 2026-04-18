# 文件路径：backend/app/models/schemas.py
# 用途：全局 Pydantic 数据模型，覆盖所有接口的输入输出
# MVP 范围：完整定义，与 PRD V1.0 + 已确认变更对齐

from __future__ import annotations
from pydantic import BaseModel, Field, model_validator
from typing import Optional
from enum import Enum
import time
import uuid


# ============ 枚举 ============

class Industry(str, Enum):
    GENERAL = "通用"
    MANUFACTURING = "制造"
    RETAIL = "零售"
    FINANCE = "金融"
    HEALTHCARE = "医疗"
    EDUCATION = "教育"
    INTERNET = "互联网"
    ECOMMERCE = "电商"


class SpeechStyle(str, Enum):
    PROFESSIONAL = "专业严谨"
    FRIENDLY = "亲和友好"
    CONCISE = "简洁直接"


class FallbackReason(str, Enum):
    NONE = "none"
    LLM_TIMEOUT = "llm_timeout"
    LLM_ERROR = "llm_error"
    NO_KNOWLEDGE = "no_knowledge"


class ChunkStatus(str, Enum):
    COMPLETED = "completed"
    PROCESSING = "processing"
    FAILED = "failed"


# ============ 知识库切片 ============

class KnowledgeChunk(BaseModel):
    """知识库切片 - 存储层数据结构"""
    chunk_id: str = Field(default_factory=lambda: f"chunk_{uuid.uuid4().hex[:12]}")
    content: str = Field(..., description="切片文本内容")
    file_id: str = Field(default="", description="来源文件 ID")
    file_name: str = Field(default="", description="来源文件名")
    category: str = Field(default="未分类", description="分类标签")
    industry: str = Field(default="通用", description="适用行业")
    created_at: str = Field(
        default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    )


# ============ 知识库管理 API ============

class UploadResponse(BaseModel):
    file_id: str
    file_name: str
    status: str = "completed"  # MVP 同步处理，直接返回 completed
    chunk_count: int


class ChunkListResponse(BaseModel):
    total: int
    chunks: list[KnowledgeChunk]


class ChunkUpdateRequest(BaseModel):
    """编辑切片请求 - 只支持改文本"""
    content: str = Field(..., min_length=1, max_length=500, description="修改后的切片文本")


class ChunkUpdateResponse(BaseModel):
    chunk_id: str
    status: str = "completed"  # MVP 同步重新 Embedding


class SearchTestRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)


class SearchTestResult(BaseModel):
    chunk_id: str
    content: str
    score: float


class SearchTestResponse(BaseModel):
    results: list[SearchTestResult]


# ============ 核心链路：建议请求/响应 ============

class SuggestRequest(BaseModel):
    """POST /api/v1/suggestions 请求体"""
    input_text: str = Field(..., min_length=1, max_length=500, description="客户说的话")
    industry: str = Field(default="通用")
    style: str = Field(default="专业严谨")
    session_id: Optional[str] = Field(default=None, description="会话 ID")
    history_inputs: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="前端缓存的最近 3 轮历史输入"
    )
    # ===== 新增：会议摘要 =====
    session_summary: str = Field(default="", description="会议摘要，≤200字")
    # ==========================
    # LLM 动态配置（前端传入，可选，不传则用服务端默认值）
    llm_base_url: Optional[str] = Field(default=None, description="LLM API Base URL")
    llm_api_key: Optional[str] = Field(default=None, description="LLM API Key")
    llm_model: Optional[str] = Field(default=None, description="LLM 模型名")


class Suggestion(BaseModel):
    """单条建议"""
    id: str = Field(default_factory=lambda: f"sug_{uuid.uuid4().hex[:6]}")
    text: str = Field(..., description="建议话术文本")
    source: str = Field(default="general", description="knowledge_base 或 general")
    ref_chunk_id: Optional[str] = Field(default=None, description="引用的知识切片 ID")


class SuggestResponse(BaseModel):
    """POST /api/v1/suggestions 响应体"""
    suggestions: list[Suggestion] = Field(default_factory=list)
    latency_ms: int = Field(default=0)
    fallback: bool = Field(default=False, description="是否降级")
    fallback_reason: FallbackReason = Field(default=FallbackReason.NONE)
    error: Optional[str] = Field(default=None)
    message: Optional[str] = Field(default=None)


# ============ 后端内部模型（不暴露给前端） ============

class LLMInternalOutput(BaseModel):
    """LLM 结构化输出 - 内部使用，含意图识别"""
    intent: str = Field(default="未识别")
    entities: dict = Field(default_factory=dict)
    suggestions: list[LLMSuggestionItem] = Field(default_factory=list)


class LLMSuggestionItem(BaseModel):
    """LLM 返回的单条建议（内部结构）"""
    text: str
    ref_chunk_id: Optional[str] = None
    source: str = "general"


# 解决前向引用
LLMInternalOutput.model_rebuild()


# ============ 文件管理 ============

class FileInfo(BaseModel):
    file_id: str
    file_name: str
    chunk_count: int
    created_at: str
    status: ChunkStatus = ChunkStatus.COMPLETED


class FileListResponse(BaseModel):
    total: int
    files: list[FileInfo]


# ============ LLM 配置（前端保存/读取用） ============

class LLMConfig(BaseModel):
    """前端 ConfigDrawer 中的 LLM 高级配置"""
    base_url: str = "https://api.deepseek.com"
    api_key: str = ""
    model: str = "deepseek-chat"


# ============ 会议摘要 API ============

class SummaryRequest(BaseModel):
    """POST /api/v1/suggestions/summary 请求体"""
    inputs: list[str] = Field(..., description="需要摘要的对话列表")
    existing_summary: str = Field(default="", description="已有摘要，增量合并用")
    llm_base_url: Optional[str] = Field(default=None)
    llm_api_key: Optional[str] = Field(default=None)
    llm_model: Optional[str] = Field(default=None)


class SummaryResponse(BaseModel):
    """POST /api/v1/suggestions/summary 响应体"""
    summary: str = Field(default="", description="生成的摘要文本，≤150字")
    latency_ms: int = Field(default=0)

# ============ 批量导入 ============

class KnowledgeBatchImportItem(BaseModel):
    """单条导入项，兼容五种卡片类型"""
    type: str = Field(default="sales_script", description="product_card / combo_card / sales_script / cs_card / lifecycle_card / industry_deep_dive")
    industry: str = Field(default="通用")
    keywords: str = Field(default="")
    priority: int = Field(default=8, ge=1, le=10)
    card_id: str = Field(default="", description="卡片唯一标识")
    case_source: str = Field(default="", description="案例来源")
    # sales_script
    trigger_scene: str = Field(default="")
    content: str = Field(default="")
    suggested_response: str = Field(default="")
    category: str = Field(default="")
    stage: str = Field(default="")
    # product_card
    product: str = Field(default="")
    pain_points: str = Field(default="")
    use_cases: list = Field(default_factory=list)
    typical_users: str = Field(default="")
    competitor_comparison: str = Field(default="")
    one_liner: str = Field(default="")
    # combo_card
    scenario: str = Field(default="")
    recommended_combo: list[str] = Field(default_factory=list)
    combo_reason: str = Field(default="")
    implementation_outline: str = Field(default="")
    expected_value: str = Field(default="")
    deal_size_hint: str = Field(default="")
    sales_tip: str = Field(default="")
    # cs_card / lifecycle_card / industry_deep_dive 的复杂嵌套字段
    cs_category: str = Field(default="")
    lifecycle_stage: str = Field(default="")
    industry_context: str = Field(default="")
    health_signals: dict = Field(default_factory=dict)
    action_playbook: dict = Field(default_factory=dict)
    talk_track: dict = Field(default_factory=dict)
    expansion_hooks: str = Field(default="")
    risk_mitigation: str = Field(default="")
    reference_case: str = Field(default="")
    industry_specific_metrics: dict = Field(default_factory=dict)
    # industry_deep_dive 专用
    industry_overview: str = Field(default="")
    org_structure: dict = Field(default_factory=dict)
    data_landscape: dict = Field(default_factory=dict)
    fanruan_penetration: dict = Field(default_factory=dict)
    competitive_landscape: dict = Field(default_factory=dict)
    budget_cycle: dict = Field(default_factory=dict)

    class Config:
        # 允许额外字段传入（不会报错）
        extra = "allow"

    @model_validator(mode='before')
    @classmethod
    def normalize_product_card(cls, data):
        """兼容 product_name → product，pain_points 数组 → 字符串"""
        if isinstance(data, dict):
            # product_name → product
            if 'product_name' in data and not data.get('product'):
                data['product'] = data.pop('product_name')
            # pain_points 数组 → 字符串
            if isinstance(data.get('pain_points'), list):
                data['pain_points'] = '、'.join(data['pain_points'])
        return data


class BatchImportRequest(BaseModel):
    items: list[KnowledgeBatchImportItem]


class BatchImportResponse(BaseModel):
    total: int
    imported: int
    failed: int
    errors: list[str] = Field(default_factory=list)
