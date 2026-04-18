# 文件路径：backend/app/models/exceptions.py
# 用途：统一异常类体系
# 变更：新增文件（评审修复）


class JisoulException(Exception):
    """机魂基础异常"""
    def __init__(self, message: str, error_code: str = "INTERNAL_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class VectorStoreError(JisoulException):
    """向量库服务故障"""
    def __init__(self, message: str = "知识库服务暂时不可用"):
        super().__init__(message, "VECTOR_STORE_ERROR")


class VectorStoreTimeout(JisoulException):
    """向量库检索超时"""
    def __init__(self, message: str = "知识库检索超时"):
        super().__init__(message, "VECTOR_STORE_TIMEOUT")


class LLMError(JisoulException):
    """LLM 调用失败"""
    def __init__(self, message: str = "AI 服务暂时不可用"):
        super().__init__(message, "LLM_ERROR")


class LLMTimeoutError(JisoulException):
    """LLM 调用超时"""
    def __init__(self, message: str = "AI 服务响应超时"):
        super().__init__(message, "LLM_TIMEOUT")


class FileProcessError(JisoulException):
    """文件处理失败"""
    def __init__(self, message: str = "文件处理失败"):
        super().__init__(message, "FILE_PROCESS_ERROR")