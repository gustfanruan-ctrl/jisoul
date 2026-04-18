# 文件路径：backend/app/knowledge/chunker.py
# 用途：文档文本提取 + 切片
# MVP 范围：支持 .txt / .md / .docx，按段落优先 + 固定长度兜底
# 不支持 PDF（已确认毙掉）

import os
import re
from typing import Optional
from loguru import logger

from app.config import settings


def extract_text(file_path: str, file_name: str) -> str:
    """从文件提取纯文本

    Args:
        file_path: 文件磁盘路径
        file_name: 原始文件名（用于判断扩展名）

    Returns:
        提取出的纯文本

    Raises:
        ValueError: 不支持的文件格式
    """
    ext = os.path.splitext(file_name)[1].lower()

    if ext in (".txt", ".md"):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    elif ext == ".docx":
        try:
            from docx import Document
            doc = Document(file_path)
            paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            return "\n\n".join(paragraphs)
        except Exception as e:
            logger.error(f"DOCX 解析失败: {e}")
            raise ValueError(f"DOCX 文件解析失败: {e}")

    else:
        raise ValueError(f"不支持的文件格式: {ext}，仅支持 .txt / .md / .docx")


def chunk_text(
    text: str,
    chunk_size: int = None,
    chunk_overlap: int = None,
) -> list[str]:
    """将文本切片

    策略：
    1. 先按段落（双换行）分割
    2. 如果单段落长度 ≤ chunk_size，保持原段落
    3. 如果单段落长度 > chunk_size，按 chunk_size 固定窗口滑动切分
    4. 过短的段落（< 20 字）与下一段合并，避免碎片化
    5. 最终去掉空切片

    Args:
        text: 完整文本
        chunk_size: 切片最大字符数，默认取配置
        chunk_overlap: 重叠字符数，默认取配置

    Returns:
        切片列表
    """
    if chunk_size is None:
        chunk_size = settings.CHUNK_SIZE
    if chunk_overlap is None:
        chunk_overlap = settings.CHUNK_OVERLAP

    if not text or not text.strip():
        return []

    # Step 1: 按段落分割（双换行 或 单换行+空行）
    raw_paragraphs = re.split(r'\n\s*\n|\n{2,}', text.strip())
    raw_paragraphs = [p.strip() for p in raw_paragraphs if p.strip()]

    # Step 2: 合并过短段落
    merged_paragraphs = []
    buffer = ""
    for para in raw_paragraphs:
        if buffer:
            buffer = buffer + "\n" + para
        else:
            buffer = para

        if len(buffer) >= 20:  # 最小有效段落长度
            merged_paragraphs.append(buffer)
            buffer = ""

    if buffer:
        if merged_paragraphs:
            merged_paragraphs[-1] = merged_paragraphs[-1] + "\n" + buffer
        else:
            merged_paragraphs.append(buffer)

    # Step 3: 对每个段落进行切片
    chunks = []
    for para in merged_paragraphs:
        if len(para) <= chunk_size:
            chunks.append(para)
        else:
            # 固定窗口滑动切分
            start = 0
            while start < len(para):
                end = start + chunk_size
                chunk = para[start:end]
                if chunk.strip():
                    chunks.append(chunk.strip())
                start = end - chunk_overlap  # 滑动窗口

    # Step 4: 最终过滤
    chunks = [c for c in chunks if len(c) >= 10]  # 少于 10 字的切片无检索价值

    logger.info(f"文本切片完成: 原文 {len(text)} 字 → {len(chunks)} 个切片")
    return chunks


def process_file(file_path: str, file_name: str) -> list[str]:
    """端到端处理：提取文本 → 切片

    Args:
        file_path: 文件磁盘路径
        file_name: 原始文件名

    Returns:
        切片文本列表

    Raises:
        ValueError: 文件格式不支持或解析失败
    """
    text = extract_text(file_path, file_name)
    if not text.strip():
        raise ValueError("文件内容为空，无法切片")

    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("切片结果为空，请检查文件内容")

    return chunks