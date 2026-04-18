# JiSoul MVP 部署手册

> 智能销售助手 - 基于大模型 + RAG 的销售话术推荐系统
> 
> 版本：v1.0 | 更新日期：2026-04-17

---

## 目录

1. [项目概述](#项目概述)
2. [环境要求](#环境要求)
3. [后端部署](#后端部署)
4. [前端部署](#前端部署)
5. [Docker 部署](#docker-部署)
6. [配置说明](#配置说明)
7. [API 端点](#api-端点)
8. [常见问题](#常见问题)

---

## 项目概述

JiSoul MVP 是一个智能销售助手系统，核心功能：

- **RAG 检索**：基于 ChromaDB + sentence-transformers 的向量检索
- **大模型生成**：调用 DeepSeek API 生成销售话术
- **前端界面**：React + Ant Design 的交互界面

**技术栈**：

| 层级 | 技术 |
|------|------|
| 后端框架 | Python 3.12 + FastAPI |
| 向量数据库 | ChromaDB (持久化) |
| Embedding | sentence-transformers (BGE-small-zh-v1.5) |
| 大模型 | DeepSeek API (deepseek-chat) |
| 前端框架 | React 19 + TypeScript + Vite |
| UI 组件 | Ant Design 5.x |
| 状态管理 | Zustand |

---

## 环境要求

### 必需环境

| 软件 | 版本要求 | 检查命令 |
|------|----------|----------|
| Python | 3.12+ | `python --version` |
| Node.js | 22+ 或 24+ | `node --version` |
| npm | 10+ | `npm --version` |

### 推荐环境

- **操作系统**：Windows 11 / macOS / Linux
- **内存**：≥ 8GB（向量检索需加载模型）
- **磁盘**：≥ 2GB（模型缓存 + ChromaDB 数据）

---

## 后端部署

### 步骤 1：进入后端目录

```bash
cd jisoul-mvp/backend
```

### 步骤 2：创建虚拟环境（推荐）

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 步骤 3：安装依赖

```bash
pip install -r requirements.txt
```

**核心依赖**：

```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
chromadb>=0.5.0
sentence-transformers>=3.0.0
torch>=2.6.0
httpx>=0.27.0
pydantic>=2.10.0
loguru>=0.7.0
python-dotenv>=1.0.0
```

### 步骤 4：配置环境变量

创建 `app/.env` 文件（或编辑已有文件）：

```env
# DeepSeek API 配置（必需）
DEEPSEEK_API_KEY=sk-your-api-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# RAG 配置（可选修改）
RAG_TOP_K=10
RAG_SIMILARITY_THRESHOLD=0.5

# 服务配置（可选修改）
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG_MODE=true
```

**获取 DeepSeek API Key**：
1. 访问 https://platform.deepseek.com/
2. 注册账号 → API Keys → 创建新 Key
3. 复制 Key 替换 `sk-your-api-key-here`

### 步骤 5：准备数据目录

确保以下目录存在（已预创建）：

```bash
# 数据目录结构
backend/data/
├── chroma/          # ChromaDB 持久化目录
├── uploads/         # 上传文件临时目录
└── sensitive_words.json  # 敏感词表

backend/models/
└── embedding/       # Embedding 模型缓存目录
```

### 步骤 6：启动后端服务

```bash
# 开发模式（带热重载）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**验证启动成功**：

```bash
# 访问健康检查端点
curl http://localhost:8000/health

# 预期响应
{"status": "healthy", "timestamp": "..."}
```

---

## 前端部署

### 步骤 1：进入前端目录

```bash
cd jisoul-mvp/frontend
```

### 步骤 2：安装依赖

```bash
npm install
```

**核心依赖**：

```
react@19.x
react-dom@19.x
antd@5.x
zustand@5.x
axios@1.x
typescript@5.x
vite@6.x
```

### 步骤 3：配置后端地址（可选）

编辑 `src/api/config.ts`：

```typescript
const API_BASE_URL = process.env.VITE_API_URL || 'http://localhost:8000';
```

或通过环境变量：

```bash
# 创建 .env.local
VITE_API_URL=http://your-backend-host:8000
```

### 步骤 4：启动前端开发服务

```bash
npm run dev
```

访问 http://localhost:5173

### 步骤 5：生产构建（可选）

```bash
npm run build
```

构建产物在 `dist/` 目录，可部署到静态服务器。

---

## Docker 部署

### 使用 docker-compose（推荐）

项目已包含 `docker-compose.yml`：

```bash
cd jisoul-mvp

# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 单独构建镜像

**后端镜像**：

```bash
cd jisoul-mvp/backend
docker build -t jisoul-backend .
docker run -p 8000:8000 -e DEEPSEEK_API_KEY=sk-xxx jisoul-backend
```

**前端镜像**：

```bash
cd jisoul-mvp/frontend
docker build -t jisoul-front .
docker run -p 80:80 jisoul-front
```

---

## 配置说明

### 后端配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `DEEPSEEK_API_KEY` | - | DeepSeek API 密钥（必需） |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | API 地址 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 模型名称 |
| `RAG_TOP_K` | `10` | 检索返回条数 |
| `RAG_SIMILARITY_THRESHOLD` | `0.5` | 相似度阈值 |
| `APP_HOST` | `0.0.0.0` | 服务监听地址 |
| `APP_PORT` | `8000` | 服务端口 |
| `DEBUG_MODE` | `true` | 调试模式 |

### 前端配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `VITE_API_URL` | `http://localhost:8000` | 后端 API 地址 |

---

## API 端点

### 核心端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/api/chat` | POST | 对话生成（核心接口） |
| `/api/knowledge/upload` | POST | 上传知识文档 |
| `/api/knowledge/list` | GET | 知识库列表 |
| `/api/knowledge/delete` | DELETE | 删除知识条目 |

### `/api/chat` 请求示例

```json
{
  "query": "客户说预算不够，怎么说服他买 FineBI？",
  "industry": "制造业",
  "chat_history": []
}
```

### `/api/chat` 响应示例

```json
{
  "reply": "您看，其实预算这事儿咱得换个角度想...",
  "sources": [
    {
      "chunk_id": "xxx",
      "content": "...",
      "score": 0.82,
      "metadata": {
        "type": "sales_script",
        "industry": "制造业"
      }
    }
  ],
  "elapsed_ms": 1200
}
```

---

## 常见问题

### Q1: Embedding 模型下载慢？

**原因**：sentence-transformers 首次运行需下载 BGE-small-zh-v1.5 模型（约 100MB）

**解决**：
1. 确保网络畅通（可访问 HuggingFace）
2. 或手动下载模型到 `models/embedding/` 目录
3. 设置环境变量：`SENTENCE_TRANSFORMERS_HOME=./models/embedding`

### Q2: DeepSeek API 报错 401？

**原因**：API Key 无效或未配置

**解决**：
1. 检查 `app/.env` 中 `DEEPSEEK_API_KEY` 是否正确
2. 确保 Key 以 `sk-` 开头
3. 登录 DeepSeek 平台确认 Key 状态

### Q3: ChromaDB 初始化失败？

**原因**：持久化目录权限问题或路径错误

**解决**：
1. 确保 `data/chroma/` 目录存在且有写权限
2. Windows 下检查路径是否含特殊字符
3. 删除 `data/chroma/` 目录重新启动（会重建数据库）

### Q4: 前端连接后端失败？

**原因**：跨域问题或地址配置错误

**解决**：
1. 确认后端已启动并监听 `0.0.0.0:8000`
2. 检查前端 `.env.local` 中 `VITE_API_URL`
3. 后端已配置 CORS，允许跨域请求

### Q5: 检索结果为空？

**原因**：知识库未导入数据或阈值过高

**解决**：
1. 通过 `/api/knowledge/upload` 上传知识文档
2. 检查 ChromaDB 数据目录是否有内容
3. 降低 `RAG_SIMILARITY_THRESHOLD`（如 0.3）

### Q6: Python 版本兼容问题？

**现状**：已适配 Python 3.12 + Node.js 22/24

**依赖兼容**：
- `sentence-transformers>=3.0.0` ✓ 支持 Python 3.12
- `torch>=2.6.0` ✓ 支持 Python 3.12
- `chromadb>=0.5.0` ✓ 支持 Python 3.12

---

## 快速启动脚本

项目已包含 `start.bat`（Windows）：

```bash
# Windows 双击运行
start.bat

# 或命令行执行
.\start.bat
```

脚本会自动：
1. 检查 Python/Node 环境
2. 安装后端依赖
3. 安装前端依赖
4. 启动后端服务
5. 启动前端服务

---

## 目录结构

```
jisoul-mvp/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── config.py            # 配置管理
│   │   ├── .env                 # 环境变量
│   │   ├── services/
│   │   │   ├── rag_service.py   # RAG 检索服务
│   │   │   ├── llm_service.py   # 大模型服务
│   │   │   └── prompt_builder.py # Prompt 构建
│   │   ├── knowledge/
│   │   │   ├── embedder.py      # Embedding 服务
│   │   │   ├── store.py         # ChromaDB 存储
│   │   │   └── chunker.py       # 文档分块
│   │   └── routers/
│   │       ├── chat.py          # 对话接口
│   │       └── knowledge.py     # 知识管理接口
│   ├── data/
│   │   ├── chroma/              # ChromaDB 数据
│   │   ├── uploads/             # 上传文件
│   │   └── sensitive_words.json # 敏感词表
│   ├── models/
│   │   └── embedding/           # 模型缓存
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/                 # API 请求
│   │   ├── components/          # UI 组件
│   │   ├── stores/              # Zustand 状态
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml
├── start.bat
└── DEPLOYMENT.md                # 本文档
```

---

## 技术支持

如遇问题，请检查：

1. 后端日志：`backend/logs/` 目录
2. 前端控制台：浏览器 DevTools
3. ChromaDB 状态：`data/chroma/` 目录是否有文件

---

**部署完成！** 🎉