"""
usage_service 存储层迁移测试

验证 usage_service 不再依赖 server_lw_data_provider，
而是通过 tokens_usage_repository.query_tokens_usage 获取数据。
"""

import importlib.util
from pathlib import Path
from types import SimpleNamespace


def _load_usage_service_module():
    """直接按文件加载 usage_service，避免触发 services 包级导入副作用。"""
    project_root = Path(__file__).resolve().parents[3]
    module_path = project_root / "lifeprism" / "server" / "services" / "usage_service.py"
    spec = importlib.util.spec_from_file_location("usage_service_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_get_usage_overview_uses_tokens_usage_repository(monkeypatch):
    """get_usage_overview 应通过 tokens_usage_repository 查询，而不是旧 provider。"""
    usage_service = _load_usage_service_module()

    def _legacy_called(*args, **kwargs):
        raise AssertionError("legacy provider should not be called")

    legacy = getattr(usage_service, "server_lw_data_provider", None)
    if legacy is not None:
        monkeypatch.setattr(legacy, "get_tokens_usage", _legacy_called, raising=True)
        monkeypatch.setattr(legacy, "get_all_tokens_usage", _legacy_called, raising=True)

    query_calls = []

    def _fake_query_tokens_usage(options=None):
        query_calls.append(options)
        return (
            [
                {
                    "session_id": "c-2026-01-15",
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "total_tokens": 150,
                    "search_count": 1,
                    "result_items_count": 2,
                    "mode": "classification",
                    "created_at": "2026-01-15 10:00:00",
                }
            ],
            1,
        )

    monkeypatch.setattr(
        usage_service,
        "tokens_usage_repository",
        SimpleNamespace(query_tokens_usage=_fake_query_tokens_usage),
        raising=False,
    )

    result = usage_service.get_usage_overview("2026-01-15")
    assert query_calls
    assert result.total_tokens == 150
    assert result.all_total_tokens == 150
