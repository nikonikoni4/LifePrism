"""RAG 配置契约：固定模型、凭据隔离和路径校验。"""

import importlib

import pytest
from pydantic import ValidationError

pytestmark = pytest.mark.core


@pytest.mark.parametrize(
    "field",
    ["enabled", "rerank_enabled", "index_directories", "embedding_base_url", "rerank_base_url"],
)
def test_rag_patch_rejects_explicit_null(field):
    from lifeprism.rag.config import RagSettingsPatch

    with pytest.raises(ValueError):
        RagSettingsPatch.model_validate({field: None})


def test_rag_defaults_and_keys_are_not_exposed():
    module = importlib.import_module("lifeprism.rag.config")
    from types import SimpleNamespace

    from lifeprism.server.schemas.rag_schemas import RagSettingsPatch

    values = {}
    settings = SimpleNamespace(
        get=lambda key, default=None: values.get(key, default),
        get_storage_key=lambda key: "secret-embedding" if key == "rag_embedding_api_key" else None,
    )
    response = module.read_settings(settings)
    assert response.enabled is False
    assert response.rerank_enabled is False
    assert response.index_directories == ["user", "diary"]
    assert response.embedding.configured is True
    assert response.rerank.configured is False
    assert "secret-embedding" not in response.model_dump_json()
    with pytest.raises(ValidationError):
        RagSettingsPatch(embedding_model="arbitrary")


@pytest.mark.parametrize(
    "directories",
    [
        ["."],
        ["../user"],
        ["C:/user"],
        ["/user"],
        ["rag"],
        ["user", "user"],
        ["user", "user/nested"],
        ["user", "USER/nested"],
    ],
)
def test_reject_unsafe_or_overlapping_directories(directories):
    from lifeprism.server.schemas.rag_schemas import RagSettingsPatch

    with pytest.raises(ValidationError):
        RagSettingsPatch(index_directories=directories)


def test_enabling_requires_matching_key():
    module = importlib.import_module("lifeprism.rag.config")
    from types import SimpleNamespace

    from lifeprism.server.schemas.rag_schemas import RagSettingsPatch

    settings = SimpleNamespace(
        get=lambda key, default=None: default, get_storage_key=lambda key: None
    )
    with pytest.raises(ValueError, match="embedding"):
        module.validate_update(settings, RagSettingsPatch(enabled=True))
    with pytest.raises(ValueError, match="rerank"):
        module.validate_update(settings, RagSettingsPatch(rerank_enabled=True))
