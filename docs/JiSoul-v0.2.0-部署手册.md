# JiSoul v0.2.0 部署手册

> RAG 高精度检索增强版
>
> 版本：v0.2.0 | 更新日期：2026-04-18

---

## 版本更新说明

### v0.2.0 核心改进

| 改进项 | 说明 | 效果 |
|--------|------|------|
| **Re-ranking 精排** | Cross-Encoder 重排序 | 语义匹配精度提升 10-15% |
| **关键词匹配增强** | 利用 JSON 的 `keywords` 字段 | 行业化问题精准召回 |
| **优先级加权** | 利用 JSON 的 `priority` 字段 | 高价值卡片优先返回 |
| **意图精准过滤** | 意图 → 卡片类型精准映射 | 解决"多样性稀释精准卡片"问题 |
| **Embedding 升级** | `bge-base` → `bge-large-zh-v1.5` | 语义理解能力提升 |

### 解决的问题

1. **JSON 标签未利用**：keywords、priority、type 等字段现在被充分利用
2. **行业化问题检索不准**：通过意图识别 + 类型精准过滤解决
3. **检索结果分散**：Re-ranking 精排 + 条件触发优化

---

## 目录

1. [改动文件清单](#1-改动文件清单)
2. [环境要求](#2-环境要求)
3. [文件替换步骤](#3-文件替换步骤)
4. [重建向量索引](#4-重建向量索引)
5. [启动验证](#5-启动验证)
6. [API 端点说明](#6-api-端点说明)
7. [配置参数](#7-配置参数)
8. [常见问题](#8-常见问题)

---

## 1. 改动文件清单

### 替换文件（3个）

| 文件路径 | 改动内容 |
|-----------|---------|
| `backend/app/config.py` | Embedding 升级 large + Reranker 配置 + RAG 参数调整 |
| `backend/app/main.py` | Reranker 预加载 + 注册增强版路由 |
| `backend/app/services/rag_service.py` | 集成条件触发 Re-ranking |

### 新增文件（5个）

| 文件路径 | 功能 |
|-----------|------|
| `backend/app/services/reranker.py` | Cross-Encoder Re-ranking 服务 |
| `backend/app/services/intent_filter.py` | 意图关键词识别 |
| `backend/app/services/metadata_enhanced_search.py` | **核心**：关键词匹配 + 优先级加权 + 意图精准过滤 |
| `backend/app/services/rag_service_enhanced.py` | 增强版 RAG（可选） |
| `backend/app/api/routes_suggestion_enhanced.py` | 增强版 API 端点 |

### 不改动文件

| 文件 | 说明 |
|------|------|
| `backend/requirements.txt` | 已兼容（sentence-transformers 支持 embedding + reranker） |
| `backend/app/services/prompt_builder.py` | 无需改动 |
| `backend/app/services/llm_service.py` | 无需改动 |
| `backend/app/api/routes_suggestion.py` | 保留，新增增强版端点 |
| `backend/app/knowledge/*` | 无需改动 |

---

## 2. 环境要求

### 必需环境

| 软件 | 版本要求 | 检查命令 |
|------|----------|----------|
| Python | 3.12+ | `python --version` |
| pip | 最新版 | `pip --version` |

### 硬件要求（新增）

| 资源 | v0.1.0 | v0.2.0 | 说明 |
|------|--------|--------|------|
| 内存 | ≥8GB | **≥12GB** | Embedding + Reranker 模型加载 |
| 磁盘 | ≥2GB | **≥4GB** | 模型缓存增加 |
| GPU | 可选 | 可选 | 有 GPU 则加速模型推理 |

### 依赖安装

```bash
# 进入后端目录
cd jisoul/backend

# 安装依赖（sentence-transformers 已包含）
pip install -r requirements.txt

# 确认关键依赖版本
pip show sentence-transformers pydantic-settings chromadb
```

**核心依赖版本要求**：
```
sentence-transformers >= 3.0.0  # 支持 embedding + reranker
pydantic-settings >= 2.0.0
chromadb >= 0.5.0
torch >= 2.6.0
```

---

## 3. 文件替换步骤

### Step 1：备份原文件

```bash
cd jisoul/backend/app

# 备份需要替换的文件
mkdir -p backup
cp config.py backup/config.py.v0.1.0
cp main.py backup/main.py.v0.1.0
cp services/rag_service.py backup/rag_service.py.v0.1.0

echo "备份完成：backup/ 目录"
```

### Step 2：复制新文件

将改动文件复制到对应位置：

**替换文件（覆盖原文件）**：
```bash
# 假设改动文件在临时目录 temp_files/

cp temp_files/backend/app/config.py backend/app/config.py
cp temp_files/backend/app/main.py backend/app/main.py
cp temp_files/backend/app/services/rag_service.py backend/app/services/rag_service.py
```

**新增文件（创建新文件）**：
```bash
cp temp_files/backend/app/services/reranker.py backend/app/services/reranker.py
cp temp_files/backend/app/services/intent_filter.py backend/app/services/intent_filter.py
cp temp_files/backend/app/services/metadata_enhanced_search.py backend/app/services/metadata_enhanced_search.py
cp temp_files/backend/app/services/rag_service_enhanced.py backend/app/services/rag_service_enhanced.py
cp temp_files/backend/app/api/routes_suggestion_enhanced.py backend/app/api/routes_suggestion_enhanced.py
```

### Step 3：确认目录结构

```bash
# 检查目录结构
ls -la backend/app/
ls -la backend/app/services/
ls -la backend/app/api/
```

**预期输出**：
```
backend/app/
├── config.py          [已替换]
├── main.py            [已替换]
├── api/
│   ├── routes_suggestion.py         [不变]
│   ├── routes_suggestion_enhanced.py [新建]
│   └── routes_knowledge.py          [不变]
├── services/
│   ├── rag_service.py               [已替换]
│   ├── reranker.py                  [新建]
│   ├── intent_filter.py             [新建]
│   ├── metadata_enhanced_search.py  [新建]
│   ├── rag_service_enhanced.py      [新建]
│   ├── prompt_builder.py            [不变]
│   ├── llm_service.py               [不变]
│   └── post_processor.py            [不变]
├── knowledge/
│   ├── embedder.py                  [不变]
│   ├── store.py                     [不变]
│   └── chunker.py                   [不变]
└── models/
    ├── schemas.py                   [不变]
    └── exceptions.py                [不变]
```

---

## 4. 重建向量索引（关键！）

**Embedding 模型从 `bge-base-zh-v1.5` 升级到 `bge-large-zh-v1.5`，必须重建向量索引。**

### Step 1：清空旧向量数据

```bash
cd jisoul/backend

# 清空 ChromaDB 数据
rm -rf data/chroma/*

# 确认清空
ls -la data/chroma/  # 应为空目录或不存在
```

### Step 2：重新导入知识库

**方式 A：使用 upload.py（推荐）**
```bash
cd jisoul/backend

# 确保 jisoul_knowledge_optimized.json 在正确位置
ls -la jisoul_knowledge_optimized.json

# 运行导入脚本
python upload.py

# 或指定文件
python upload.py --file jisoul_knowledge_optimized.json
```

**方式 B：使用 seed.py**
```bash
python -m app.knowledge.seed --rebuild
```

### Step 3：确认导入成功

```bash
# 检查 ChromaDB 数据目录
ls -la data/chroma/

# 应看到类似：
# chroma.sqlite3  collections/  ...
```

**预期导入条目数**：
- 原知识库：493 条卡片
- 切片后：约 500-800 条（取决于切片策略）

---

## 5. 启动验证

### Step 1：配置环境变量

```bash
cd jisoul/backend

# 创建/编辑 .env 文件
cat > app/.env << EOF
# DeepSeek API 配置
DEEPSEEK_API_KEY=sk-your-api-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# RAG 配置
RAG_TOP_K=15
RAG_SIMILARITY_THRESHOLD=0.35
RERANK_ENABLED=true
EOF
```

### Step 2：启动服务

```bash
cd jisoul/backend

# 开发模式启动
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式启动
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Step 3：检查启动日志

**预期启动日志**：
```
=== 机魂 MVP v0.2.0 启动 ===
预加载 Embedding 模型...
加载 Embedding 模型: BAAI/bge-large-zh-v1.5 ...
Embedding 模型加载成功 (sentence-transformers)
预加载 Reranker 模型...
加载 Reranker 模型: BAAI/bge-reranker-base ...
Reranker 模型加载成功
初始化向量数据库...
初始化 Chroma，持久化路径: ./data/chroma
Chroma collection 'jisoul_knowledge' 已就绪，当前 500 条记录
LLM API Key 已配置
=== 应用启动完成 ===
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**启动耗时预估**：
- Embedding 加载：~15 秒（bge-large）
- Reranker 加载：~5-8 秒
- 总启动时间：~25-30 秒

### Step 4：健康检查

```bash
# 访问健康检查端点
curl http://localhost:8000/health

# 预期响应
{
  "status": "healthy",
  "app": "机魂 MVP",
  "version": "0.2.0",
  "vector_count": 500
}

# 访问 API 文档
curl http://localhost:8000/docs
```

---

## 6. API 端点说明

### 端点列表

| 端点 | 方法 | 说明 | 版本 |
|------|------|------|------|
| `/health` | GET | 健康检查 | v0.1.0 |
| `/api/v1/suggestions` | POST | 基础版建议话术 | v0.1.0 |
| `/api/v1/suggestions/enhanced` | POST | **增强版建议话术** | **v0.2.0 新增** |
| `/api/v1/knowledge/upload` | POST | 上传知识文档 | v0.1.0 |
| `/api/v1/knowledge/list` | GET | 知识库列表 | v0.1.0 |

### 增强版端点请求示例

```bash
curl -X POST http://localhost:8000/api/v1/suggestions/enhanced \
  -H "Content-Type: application/json" \
  -d '{
    "input_text": "制造业客户说预算不够，怎么说服他买FineBI?",
    "industry": "制造业",
    "style": "专业严谨"
  }'
```

**预期响应**：
```json
{
  "suggestions": [
    {
      "id": "sug_abc123",
      "text": "其实预算这事儿咱得换个角度想...",
      "source": "knowledge_base",
      "ref_chunk_id": "互联网科技_sales_script_001"
    },
    ...
  ],
  "latency_ms": 350,
  "fallback": false,
  "fallback_reason": "NONE"
}
```

### 测试场景建议

| 测试问题 | 预期效果 |
|---------|---------|
| "制造业客户说预算不够" | 精准召回 `sales_script` + `combo_card`，含"预算"/"价格"关键词 |
| "和永洪BI对比有什么优势" | 精准召回 `product_card`，含"竞品"/"对比"关键词 |
| "数据分散想做数据平台" | 精准召回 `combo_card`（FDL+FineBI组合） |
| "实施周期多久" | 精准召回 `implementation_guide` |
| "客户流失怎么分析" | 精准召回 `cs_card` + `lifecycle_card` |

---

## 7. 配置参数

### config.py 关键参数

```python
# ============ Embedding ============
EMBEDDING_MODEL_NAME: str = "BAAI/bge-large-zh-v1.5"  # 升级为 large
EMBEDDING_MODEL_CACHE_DIR: str = "./models/embedding"

# ============ Re-ranking ============
RERANKER_MODEL_NAME: str = "BAAI/bge-reranker-base"   # 轻量模型
RERANKER_MAX_LENGTH: int = 512
RERANK_MIN_CANDIDATES: int = 5                        # 最少候选数触发
RERANK_SCORE_SPREAD_THRESHOLD: float = 0.08           # Top3分散阈值
RERANK_LOW_CONFIDENCE_THRESHOLD: float = 0.55         # Top1不确信阈值
RERANK_ENABLED: bool = True                            # 是否启用

# ============ RAG 参数 ============
RAG_TOP_K: int = 15         # 粗排候选数（减少降低延迟）
RAG_SIMILARITY_THRESHOLD: float = 0.35  # 阈值放宽（配合rerank）
RAG_FINAL_K: int = 10      # 最终返回条数
```

### 环境变量覆盖

可通过 `.env` 文件覆盖：
```env
RERANK_ENABLED=false        # 关闭 rerank 测试对比
RAG_TOP_K=20                # 增加候选数
RAG_SIMILARITY_THRESHOLD=0.4
```

---

## 8. 常见问题

### Q1: 模型下载慢？

**原因**：首次启动需下载 bge-large-zh-v1.5（约 1.3GB）和 bge-reranker-base（约 400MB）

**解决**：
```bash
# 使用镜像站
export HF_ENDPOINT=https://hf-mirror.com

# 或手动下载后放入缓存目录
mkdir -p models/embedding
# 将模型文件放入 models/embedding/
```

### Q2: 内存不足？

**原因**：Embedding + Reranker 模型约占用 1.5GB 内存

**解决**：
```python
# 方案1: 回退 Embedding 模型
EMBEDDING_MODEL_NAME: str = "BAAI/bge-base-zh-v1.5"  # 约 700MB

# 方案2: 关闭 Reranker
RERANK_ENABLED: bool = False
```

### Q3: 启动报错找不到模块？

**原因**：文件路径不正确或缺少依赖

**解决**：
```bash
# 检查文件
ls backend/app/services/reranker.py
ls backend/app/services/metadata_enhanced_search.py

# 安装依赖
pip install sentence-transformers pydantic-settings
```

### Q4: 检索结果没变化？

**原因**：向量索引未重建

**解决**：
```bash
# 清空旧向量
rm -rf data/chroma/*

# 重新导入
python upload.py

# 确认条目数
curl http://localhost:8000/health | jq '.vector_count'
```

### Q5: Re-ranking 增加多少延迟？

**数据**：
- 不触发 rerank：~200ms（粗排）
- 触发 rerank：~350ms（粗排 + 精排）

**触发条件**：
- 候选分散（Top3 相似度差距 > 0.08）
- Top1 不确信（相似度 < 0.55）
- 候选数 >= 5

**关闭测试**：
```python
RERANK_ENABLED: bool = False
```

### Q6: 如何确认 JSON 标签被利用？

**查看日志**：
```
关键词匹配融合: Top3 keywords_score=[...]
优先级加权: priority=10 → final_score=0.90
意图识别: '价格异议' → 目标类型: ['sales_script', 'combo_card']
```

**Metadata过滤条件示例**：
```json
{
  "$and": [
    {"$or": [{"industry": "制造业"}, {"industry": "通用"}]},
    {"type": {"$in": ["sales_script", "combo_card"]}}
  ]
}
```

---

## 9. Docker 部署（可选）

### 使用 docker-compose

```bash
cd jisoul

# 启动所有服务
docker-compose up -d --build

# 查看日志
docker-compose logs -f backend

# 停止服务
docker-compose down
```

### 环境变量配置

```yaml
# docker-compose.yml 添加
services:
  backend:
    environment:
      - DEEPSEEK_API_KEY=sk-xxx
      - RERANK_ENABLED=true
      - RAG_TOP_K=15
```

---

## 10. 验证成功标志

| 检查项 | 预期结果 |
|--------|---------|
| 启动日志 | "Reranker 模型加载成功" |
| 向量条目数 | ≥ 400 条 |
| 增强端点响应 | latency_ms ≈ 300-400ms |
| 行业化问题 | 精准召回相关卡片（如"预算不够" → sales_script） |
| 日志关键词匹配 | 显示 keywords_score + priority_bonus |

---

## 11. 版本回退

如需回退到 v0.1.0：

```bash
cd jisoul/backend/app

# 恢复备份文件
cp backup/config.py.v0.1.0 config.py
cp backup/main.py.v0.1.0 main.py
cp backup/rag_service.py.v0.1.0 services/rag_service.py

# 删除新增文件
rm services/reranker.py
rm services/intent_filter.py
rm services/metadata_enhanced_search.py
rm services/rag_service_enhanced.py
rm api/routes_suggestion_enhanced.py

# 重建向量索引（回退 Embedding）
rm -rf data/chroma/*
python upload.py

# 重启
uvicorn app.main:app --reload
```

---

**部署完成！** 🎉