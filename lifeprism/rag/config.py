"""固定模型契约和 RAG 配置；密钥沿用 SettingsManager 安全存储。"""

from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

EMBEDDING_MODEL = "doubao-embedding-vision"
EMBEDDING_BASE_URL = "https://ark.cn-beijing.volces.com/api/plan/v3"
RERANK_MODEL = "qwen3.7-text-rerank"
RERANK_BASE_URL = "https://llm-v1wy4r670fcws401.cn-beijing.maas.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
DIMENSIONS = 2048
KEYS = {"embedding": "rag_embedding_api_key", "rerank": "rag_rerank_api_key"}


class SettingsSource(Protocol):
    """RAG 需要的配置读取接口。"""

    def get(self, key: str, default: Any = None) -> Any: ...
    def get_storage_key(self, key: str) -> str | None: ...


def validate_directories(values: list[str]) -> list[str]:
    """只接受不重叠、可移植的数据目录相对路径。"""
    result: list[str] = []
    for raw in values:
        path = PurePosixPath(raw)
        if (
            not raw
            or not path.parts
            or raw != path.as_posix()
            or "\\" in raw
            or ":" in raw
            or path.is_absolute()
            or PureWindowsPath(raw).drive
            or any(p in ("", ".", "..") for p in path.parts)
            or path.parts[0].lower() in {"rag", "config", "logs", "database", "screenshots"}
        ):
            raise ValueError("索引目录必须是数据目录内的安全相对路径")
        if any(
            PurePosixPath(raw.lower()) == PurePosixPath(p.lower())
            or PurePosixPath(raw.lower()).is_relative_to(p.lower())
            or PurePosixPath(p.lower()).is_relative_to(raw.lower())
            for p in result
        ):
            raise ValueError("索引目录不能重复或相互包含")
        result.append(raw)
    if not result:
        raise ValueError("至少选择一个索引目录")
    return result


class RagSettingsPatch(BaseModel):
    """可编辑配置；模型、地址和凭据不接受此接口更新。"""

    model_config = ConfigDict(extra="forbid")
    enabled: bool | None = None
    rerank_enabled: bool | None = None
    index_directories: list[str] | None = None

    @field_validator("enabled", "rerank_enabled", "index_directories", mode="before")
    @classmethod
    def reject_null(cls, value: Any) -> Any:
        """省略表示保留配置，显式 null 不允许清空必需设置。"""
        if value is None:
            raise ValueError("RAG 设置不可设为 null")
        return value

    @field_validator("index_directories")
    @classmethod
    def check_directories(cls, value: list[str] | None) -> list[str] | None:
        """校验显式提供的目录列表。"""
        return validate_directories(value) if value is not None else None


class ModelInfo(BaseModel):
    """固定模型及密钥配置状态，无密钥内容。"""

    model: str
    base_url: str
    configured: bool


class RagSettings(BaseModel):
    """设置界面与运行期共用的配置快照。"""

    enabled: bool = False
    rerank_enabled: bool = False
    index_directories: list[str] = Field(default_factory=lambda: ["user", "diary"])
    embedding: ModelInfo
    rerank: ModelInfo


def read_settings(source: SettingsSource) -> RagSettings:
    """读取安全配置快照，不依赖聊天服务商的 Key。"""
    return RagSettings(
        enabled=source.get("rag.enabled", False),
        rerank_enabled=source.get("rag.rerank_enabled", False),
        index_directories=source.get("rag.index_directories", ["user", "diary"]),
        embedding=ModelInfo(
            model=EMBEDDING_MODEL,
            base_url=EMBEDDING_BASE_URL,
            configured=bool(source.get_storage_key(KEYS["embedding"])),
        ),
        rerank=ModelInfo(
            model=RERANK_MODEL,
            base_url=RERANK_BASE_URL,
            configured=bool(source.get_storage_key(KEYS["rerank"])),
        ),
    )


def validate_update(source: SettingsSource, patch: RagSettingsPatch) -> None:
    """开启功能之前必须配置对应模型凭据。"""
    current = read_settings(source)
    if patch.enabled is True and not current.embedding.configured:
        raise ValueError("请先保存 embedding API Key")
    if patch.rerank_enabled is True and not current.rerank.configured:
        raise ValueError("请先保存 rerank API Key")
