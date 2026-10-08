"""RAG HTTP 请求契约。"""

from pydantic import BaseModel, ConfigDict, Field

from lifeprism.rag.config import RagSettings, RagSettingsPatch

__all__ = ["RagSettings", "RagSettingsPatch", "RagKeyRequest"]


class RagKeyRequest(BaseModel):
    """空字符串表示清除该用途的密钥。"""

    model_config = ConfigDict(extra="forbid")
    api_key: str = Field(max_length=4096, description="API Key；空字符串清除")
