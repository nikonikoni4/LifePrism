# 测试规范合规 — 标记 + 目录迁移 + Service 层测试

**Triage labels**: `ready-for-agent`
**Parent**: `.scratch/custom-records-module/PRD.md`
**Code Review**: `docs/generated/003/code-review-2026-07-07-2145.md` Issues 4, 5, 14（置信度 80-95）

## What to build

修复 3 个测试规范问题，使测试符合项目 `docs/coding-rules/test-rules.md` 规范。

端到端行为：
1. 测试文件从 `test/core/unit/repository/` 迁移到 `test/core/integration/repository/`（因涉及真实数据库操作）
2. 所有测试函数或模块级添加 `@pytest.mark.core` 标记
3. 新增 Service 层测试文件，覆盖 `get_type` 的 None 路径、`create_entry` 的边界情况等

## Acceptance criteria

- [ ] `test_custom_records_repository.py` 迁移到 `test/core/integration/repository/` 目录
- [ ] 文件顶部添加 `pytestmark = pytest.mark.core` 或每个测试类标注 `@pytest.mark.core`
- [ ] `pytest -m core` 能正确收集所有自定义记录测试
- [ ] 新增 `test/core/integration/services/test_custom_records_service.py`
- [ ] Service 测试覆盖 `get_type` 类型不存在时抛出 `EntityNotFoundError`（Issue 3 修复后）
- [ ] Service 测试覆盖 `create_entry` 正常流程
- [ ] Service 测试覆盖 `get_entries` 分页正确性（Issue 1 修复后）
- [ ] 全部测试通过，无回归

## Blocked by

- `.scratch/custom-records-module/issues/09-fix-backend-robustness.md`（Service 测试需基于修复后的行为编写）
