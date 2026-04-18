# 文件路径：backend/app/services/prompt_builder.py
# 用途：动态组装 Prompt - 合并 NLU + 话术生成为单次 LLM 调用
# MVP 范围：完整 Prompt 模板，含角色设定 + 行业 + 上下文 + 知识片段 + 反泛化约束

from typing import Optional
from loguru import logger


class PromptBuilder:
    """Prompt 动态构建器

    设计意图：
    - 单次 LLM 调用同时完成意图识别 + 话术生成
    - 硬编码反泛化约束，确保输出质量
    - 支持行业/风格/上下文动态注入
    """

    # 系统 Prompt（角色设定 + 输出格式 + 硬性约束）
    SYSTEM_PROMPT = """你是一位资深的 B2B 客户成功顾问和销售教练。你的任务是根据客户说的话，结合知识库中的专业知识，为一线销售/客户成功人员提供可以直接使用的接话建议。

输出格式要求
你必须严格按照以下 JSON 格式输出，不要输出任何其他内容：json
{
  "intent": "识别到的客户意图（如：竞品对比、价格异议、功能咨询、需求确认等）",
  "entities": {"关键实体名": "实体值"},
  "suggestions": [
    {
      "text": "建议话术1",
      "ref_chunk_id": "引用的知识切片ID，无则为null",
      "source": "knowledge_base 或 general"
    },
    {
      "text": "建议话术2",
      "ref_chunk_id": null,
      "source": "general"
    }
  ]
}
硬性约束（必须遵守）
1. 必须使用口语化表达：使用"您""咱""说实话""其实吧""您看"等口语词，让话术听起来像真人销售在聊天
2. 禁止AI味表述：禁止"作为AI助手""我建议""从技术角度来说""综合来看"等书面化、机器味表达
3. 如果知识片段中包含具体数据、产品名、功能名、对比维度，必须直接引用原文中的具体信息（如"26000多家客户""70%的500强企业都在用"）
4. 禁止输出"我们的产品很有优势""我们的方案很好"等泛化空洞表述
5. 每条建议不超过 50 字，一两句说完，不要长篇大论
6. 如果知识片段无法回答当前问题，输出转向话术，如"这个点我帮您确认一下，回头给您详细的对比数据"
7. 禁止使用"保证""绝对""承诺""100%""肯定不会"等承诺性词语
8. 生成 1-3 条建议，不多于 3 条
9. suggestions 中的 source 字段：如果该建议主要基于知识片段生成，填 "knowledge_base" 并附上 ref_chunk_id；如果是通用建议，填 "general"，ref_chunk_id 为 null"""

    def build(
        self,
        customer_input: str,
        knowledge_chunks: list[dict],
        industry: str = "通用",
        style: str = "专业严谨",
        history_inputs: list[str] = None,
        session_summary: str = "",  # ← 新增参数
    ) -> tuple[str, str]:
        """构建完整的 system prompt 和 user prompt

        Args:
            customer_input: 当前客户说的话
            knowledge_chunks: RAG 检索到的知识切片列表
            industry: 行业
            style: 话术风格
            history_inputs: 最近 3 轮历史输入
            session_summary: 会议摘要（≤200字）

        Returns:
            (system_prompt, user_prompt) 元组
        """
        # ---- User Prompt 动态组装 ----
        parts = []

        # 1. 会议摘要（新增，放在最前面）
        if session_summary and session_summary.strip():
            parts.append(f"## 会议背景摘要\n{session_summary.strip()}")

        # 2. 行业和风格
        parts.append(f"## 当前场景\n- 行业：{industry}\n- 话术风格要求：{style}")

        # 3. 对话上下文（如有）
        if history_inputs:
            history_text = "\n".join(
                [f"  第{i+1}轮：{h}" for i, h in enumerate(history_inputs)]
            )
            parts.append(f"## 对话历史（最近几轮客户说的话）\n{history_text}")

        # 4. 当前客户输入
        parts.append(f"## 客户当前说的话\n{customer_input}")

        # 5. 知识库上下文
        if knowledge_chunks:
            kb_text = self._format_knowledge_chunks(knowledge_chunks)
            parts.append(f"## 知识库参考（请优先基于以下知识生成建议）\n{kb_text}")
        else:
            parts.append(
                "## 知识库参考\n未检索到相关知识。请基于你的通用知识生成建议，"
                "并在每条建议的 source 中标注 \"general\"。"
                "如果问题很专业无法确定答案，请生成转向话术。"
            )

        # 6. 风格细化指令
        style_instruction = self._get_style_instruction(style)
        if style_instruction:
            parts.append(f"## 风格补充\n{style_instruction}")

        user_prompt = "\n\n".join(parts)

        logger.debug(
            f"Prompt 构建完成: industry={industry} style={style} "
            f"chunks={len(knowledge_chunks)} history={len(history_inputs or [])} "
            f"summary_len={len(session_summary or '')}"
        )

        return self.SYSTEM_PROMPT, user_prompt

    def _format_knowledge_chunks(self, chunks: list[dict]) -> str:
        """格式化知识切片为 Prompt 中的文本"""
        lines = []
        for i, chunk in enumerate(chunks, 1):
            chunk_id = chunk.get("chunk_id", "unknown")
            content = chunk.get("content", "")
            score = chunk.get("score", 0)
            category = chunk.get("metadata", {}).get("category", "")

            line = f"### 知识片段{i}（ID: {chunk_id}, 相关度: {score}, 分类: {category}）\n{content}"
            lines.append(line)
        return "\n\n".join(lines)

    def _get_style_instruction(self, style: str) -> str:
        """根据风格生成补充指令"""
        style_map = {
            "专业严谨": (
                "使用专业术语，语气沉稳自信，逻辑清晰。"
                "适合面对技术决策者或高管。示例语气：'从数据来看...' '根据行业实践...'"
            ),
            "亲和友好": (
                "使用轻松自然的语言，适当使用口语化表达，拉近距离。"
                "适合面对业务人员或初次接触的客户。示例语气：'其实咱们...' '很多客户一开始也...'"
            ),
            "简洁直接": (
                "直击要点，不铺垫，一句话说清楚核心价值。"
                "适合面对时间紧张的客户或决策层。示例语气：'核心区别是...' '一句话总结...'"
            ),
        }
        return style_map.get(style, "")


# 全局单例
prompt_builder = PromptBuilder()