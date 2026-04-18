# 文件路径：backend/app/services/llm_service.py
# 用途：LLM 调用服务 - 支持动态配置 API（用户自填 Key）+ 超时降级
# MVP 范围：OpenAI 兼容协议调用，10 秒超时降级
# 变更：新增 _ClientPool 类，按 base_url+api_key 缓存 AsyncOpenAI 实例（评审修复）

import json
import time
import hashlib
from typing import Optional
from loguru import logger
from openai import AsyncOpenAI

from app.config import settings


class _ClientPool:
    """AsyncOpenAI 客户端连接池

    按 (base_url, api_key) 二元组缓存客户端实例，
    避免每次请求创建新的 TCP+TLS 连接。

    ⚠️ MVP 后可能需要重构：加 LRU 淘汰、连接健康检查、最大池大小限制
    """

    def __init__(self, max_size: int = 10):
        self._pool: dict[str, AsyncOpenAI] = {}
        self._max_size = max_size

    def _make_key(self, base_url: str, api_key: str) -> str:
        """生成缓存 key（api_key 做哈希，不在内存中存明文 key 的映射）"""
        key_hash = hashlib.md5(f"{base_url}:{api_key}".encode()).hexdigest()[:12]
        return key_hash

    def get_client(
        self,
        base_url: str,
        api_key: str,
        timeout: int,
    ) -> AsyncOpenAI:
        """获取或创建客户端"""
        cache_key = self._make_key(base_url, api_key)

        if cache_key in self._pool:
            return self._pool[cache_key]

        # 池满时淘汰最早的（简单 FIFO）
        if len(self._pool) >= self._max_size:
            oldest_key = next(iter(self._pool))
            old_client = self._pool.pop(oldest_key)
            logger.debug(f"Client 池满，淘汰: {oldest_key}")
            # 不 await close，让 GC 处理
            # ⚠️ MVP 后改为异步关闭

        normalized_url = base_url if base_url.endswith("/v1") else f"{base_url}/v1"
        client = AsyncOpenAI(
            base_url=normalized_url,
            api_key=api_key,
            timeout=timeout,
        )
        self._pool[cache_key] = client
        logger.debug(f"新建 Client: {cache_key}, 池大小: {len(self._pool)}")
        return client


# 全局连接池
_client_pool = _ClientPool(max_size=10)


class LLMService:
    """LLM 调用服务

    设计意图：
    - 使用 OpenAI 兼容协议，支持 DeepSeek / 智谱 / Moonshot / Ollama
    - 前端可传入自定义 API 配置，后端动态实例化 client
    - 10 秒超时自动降级
    - 解析 LLM 返回的结构化 JSON
    """

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        llm_base_url: Optional[str] = None,
        llm_api_key: Optional[str] = None,
        llm_model: Optional[str] = None,
    ) -> Optional[dict]:
        """调用 LLM 生成话术建议

        Args:
            system_prompt: 系统角色 Prompt
            user_prompt: 用户动态 Prompt
            llm_base_url: API Base URL（可选，不传用默认）
            llm_api_key: API Key（可选，不传用默认）
            llm_model: 模型名（可选，不传用默认）

        Returns:
            解析后的字典，含 intent / entities / suggestions
            失败时返回 None
        """
        base_url = llm_base_url or settings.DEFAULT_LLM_BASE_URL
        api_key = llm_api_key or settings.DEFAULT_LLM_API_KEY
        model = llm_model or settings.DEFAULT_LLM_MODEL

        if not api_key:
            logger.error("LLM API Key 未配置")
            return None

        # 从连接池获取 client（不再每次新建）
        client = _client_pool.get_client(
            base_url=base_url,
            api_key=api_key,
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )

        start = time.time()

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=settings.LLM_MAX_TOKENS,
                temperature=settings.LLM_TEMPERATURE,
                response_format={"type": "json_object"},  # 强制 JSON 输出
            )

            elapsed_ms = int((time.time() - start) * 1000)
            raw_content = response.choices[0].message.content
            logger.info(f"LLM 调用成功: model={model} 耗时={elapsed_ms}ms")
            logger.debug(f"LLM 原始输出: {raw_content[:500]}")

            # 解析 JSON
            parsed = self._parse_response(raw_content)
            if parsed:
                parsed["_latency_ms"] = elapsed_ms
            return parsed

        except Exception as e:
            elapsed_ms = int((time.time() - start) * 1000)
            error_type = type(e).__name__
            logger.error(f"LLM 调用失败: {error_type}: {e} (耗时 {elapsed_ms}ms)")
            return None

        # 注意：不再 close client，由连接池管理生命周期

    async def generate_raw(
        self,
        system_prompt: str,
        user_prompt: str,
        llm_base_url: Optional[str] = None,
        llm_api_key: Optional[str] = None,
        llm_model: Optional[str] = None,
    ) -> Optional[str]:
        """调用 LLM 生成原始文本（不解析 JSON）

        用于摘要生成等不需要结构化输出的场景。

        Returns:
            原始文本内容，失败时返回 None
        """
        base_url = llm_base_url or settings.DEFAULT_LLM_BASE_URL
        api_key = llm_api_key or settings.DEFAULT_LLM_API_KEY
        model = llm_model or settings.DEFAULT_LLM_MODEL

        if not api_key:
            logger.error("LLM API Key 未配置")
            return None

        client = _client_pool.get_client(
            base_url=base_url,
            api_key=api_key,
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )

        start = time.time()

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=300,  # 摘要不需要太多 token
                temperature=0.3,  # 低温度保证稳定输出
                # 不设置 response_format，允许自由文本输出
            )

            elapsed_ms = int((time.time() - start) * 1000)
            raw_content = response.choices[0].message.content
            logger.info(f"LLM 调用成功(raw): model={model} 耗时={elapsed_ms}ms")

            return raw_content

        except Exception as e:
            elapsed_ms = int((time.time() - start) * 1000)
            error_type = type(e).__name__
            logger.error(f"LLM 调用失败(raw): {error_type}: {e} (耗时 {elapsed_ms}ms)")
            return None

    def _parse_response(self, raw: str) -> Optional[dict]:
        """解析 LLM 返回的 JSON

        容错策略：
        1. 直接 json.loads
        2. 尝试提取 ```json ... ``` 中的内容
        3. 失败返回 None
        """
        if not raw:
            return None

        # 尝试直接解析
        try:
            data = json.loads(raw)
            return self._validate_output(data)
        except json.JSONDecodeError:
            pass

        # 尝试提取代码块
        import re
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                return self._validate_output(data)
            except json.JSONDecodeError:
                pass

        # 尝试找到第一个 { 和最后一个 }
        start = raw.find('{')
        end = raw.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(raw[start:end + 1])
                return self._validate_output(data)
            except json.JSONDecodeError:
                pass

        logger.warning(f"LLM 输出 JSON 解析失败: {raw[:200]}")
        return None

    def _validate_output(self, data: dict) -> dict:
        """校验和标准化 LLM 输出结构"""
        result = {
            "intent": data.get("intent", "未识别"),
            "entities": data.get("entities", {}),
            "suggestions": [],
        }

        raw_suggestions = data.get("suggestions", [])
        for item in raw_suggestions[:3]:  # 最多 3 条
            if isinstance(item, str):
                # LLM 可能直接返回字符串列表而非对象列表
                result["suggestions"].append({
                    "text": item[:200],  # 截断到 200 字
                    "ref_chunk_id": None,
                    "source": "general",
                })
            elif isinstance(item, dict):
                text = item.get("text", "")
                if not text:
                    continue
                result["suggestions"].append({
                    "text": text[:200],
                    "ref_chunk_id": item.get("ref_chunk_id"),
                    "source": item.get("source", "general"),
                })

        return result


# 全局单例
llm_service = LLMService()