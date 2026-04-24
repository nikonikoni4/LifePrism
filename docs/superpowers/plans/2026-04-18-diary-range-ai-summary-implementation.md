---
version: 1.0
created_at: 2026-04-18
updated_at: 2026-04-18
last_updated: 创建日记范围手动总结实施计划
abstract: 规划日记范围手动总结功能的实施步骤，覆盖 diary_source_hash、behavior.md 次级标题工具、批量更新 API、前端设置入口和验证流程。
title: Diary Range AI Summary Implementation Plan
status: active
related_spec: docs/superpowers/specs/2026-04-18-diary-range-ai-summary-design.md
---

# Diary Range AI Summary Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add date-range manual diary AI summary updates in the journal settings menu, while tracking whether an existing summary still matches the current diary content with `diary_source_hash`.

**Architecture:** Keep the existing single-day regeneration flow intact, and add a dedicated backend batch endpoint that owns range filtering, `diary_source_hash` comparison, and `behavior.md` writes. Refactor the markdown utility to enforce `## date -> ### subheading` structure so `behavior.md` remains a structured aggregate file instead of a state source.

**Tech Stack:** FastAPI, Pydantic, SQLite migrations, existing `diary_service` / `diary_provider`, React 19, TypeScript, fetch API, pytest, Vite build

---

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建实施计划 |

## File Structure

- Modify: `lifeprism/config/database.py`
- Create: `lifeprism/repository/migrations/scripts/m004_diary_source_hash.py`
- Modify: `lifeprism/repository/migrations/scripts/__init__.py`
- Modify: `lifeprism/server/schemas/diary_schemas.py`
- Modify: `lifeprism/server/providers/diary_provider.py`
- Modify: `lifeprism/server/services/diary_service.py`
- Modify: `lifeprism/server/api/diary_api.py`
- Modify: `lifeprism/llm/utils/md_os.py`
- Modify: `lifeprism/llm/utils/__init__.py`
- Modify: `lifeprism/llm/function/diary_summary.py`
- Modify: `test/core/api/test_diary_ai_summary_api.py`
- Create: `test/core/api/test_diary_ai_summary_range_api.py`
- Create: `test/core/unit/test_md_os.py`
- Modify: `frontend/apps/mindspace/components/journal/diaryTypes.ts`
- Modify: `frontend/apps/mindspace/components/journal/diaryApi.ts`
- Modify: `frontend/apps/mindspace/components/journal/SettingsPopover.tsx`
- Modify: `frontend/apps/mindspace/components/journal/journal.tsx`
- Create: `frontend/apps/mindspace/components/journal/RangeSummaryModal.tsx`
- Modify: `docs/specs/2026-04-15-mind-space-diary.md`
- Modify: `docs/superpowers/plans/index.md`

## Responsibility Notes

- `database.py` 和迁移脚本共同负责“新库建表 + 旧库补列”的完整闭环，不能只改其一。
- `md_os.py` 负责强约束 `behavior.md` 的层级结构，调用方不再手写 markdown 拼接。
- `diary_service.py` 持有正文 hash 计算、单日 summary 保存、批量筛选和三种覆盖策略。
- `diary_api.py` 只暴露批量接口和 HTTP 状态转换，不持有筛选逻辑。
- 前端通过设置菜单入口打开批量更新弹窗，日期字符串必须继续使用 `toLocalDateString` 规则。

### Task 1: Add `diary_source_hash` persistence and migration

**Files:**
- Modify: `lifeprism/config/database.py`
- Create: `lifeprism/repository/migrations/scripts/m004_diary_source_hash.py`
- Modify: `lifeprism/repository/migrations/scripts/__init__.py`
- Modify: `lifeprism/server/schemas/diary_schemas.py`
- Modify: `lifeprism/server/providers/diary_provider.py`
- Test: `test/core/api/test_diary_ai_summary_api.py`

- [ ] **Step 1: Extend the existing diary API test so a successful summary generation expects `diary_source_hash` to be written together with `ai_summary`**

```python
def test_generate_diary_ai_summary_overwrites_summary_and_source_hash(monkeypatch):
    ...
    assert updated_payloads == [{
        "ai_summary": "新总结",
        "diary_source_hash": "expected-hash",
    }]
```

- [ ] **Step 2: Run the targeted backend test and verify it fails because `diary_source_hash` does not exist yet**

Run: `python -m pytest test/core/api/test_diary_ai_summary_api.py::test_generate_diary_ai_summary_overwrites_summary_and_source_hash -v`
Expected: FAIL because provider/service does not write the new field.

- [ ] **Step 3: Add `diary_source_hash` to `DIARY_CONFIG` and the diary response schemas**

```python
'diary_source_hash': {
    'type': 'TEXT',
    'constraints': ['DEFAULT NULL'],
    'comment': '生成当前 ai_summary 时使用的正文 hash'
}
```

```python
class DiaryItem(BaseModel):
    ...
    diary_source_hash: Optional[str] = Field(default=None, description="当前 AI 总结对应的正文 hash")
```

- [ ] **Step 4: Add a migration script for existing SQLite databases and register it**

```python
VERSION = 4
NAME = "m004_diary_source_hash"


def check_if_applied(cursor) -> bool:
    cursor.execute("PRAGMA table_info(diary)")
    columns = {row[1] for row in cursor.fetchall()}
    return "diary_source_hash" in columns


def upgrade(cursor) -> None:
    cursor.execute("ALTER TABLE diary ADD COLUMN diary_source_hash TEXT DEFAULT NULL")
```

- [ ] **Step 5: Extend `diary_provider.update_diary` and conversion helpers so the new field can be persisted and returned**

```python
allowed_fields = ['mood', 'importance', 'custom_tags', 'word_count', 'ai_summary', 'diary_source_hash']
```

- [ ] **Step 6: Run the full single-day diary summary API test file**

Run: `python -m pytest test/core/api/test_diary_ai_summary_api.py -v`
Expected: PASS for the existing single-day contracts with the new hash assertion included.

- [ ] **Step 7: Commit**

```bash
git add lifeprism/config/database.py lifeprism/repository/migrations/scripts/m004_diary_source_hash.py lifeprism/repository/migrations/scripts/__init__.py lifeprism/server/schemas/diary_schemas.py lifeprism/server/providers/diary_provider.py test/core/api/test_diary_ai_summary_api.py
git commit -m "feat(diary): add diary source hash persistence"
```

### Task 2: Refactor `behavior.md` utilities to enforce `###` subheadings

**Files:**
- Modify: `lifeprism/llm/utils/md_os.py`
- Modify: `lifeprism/llm/utils/__init__.py`
- Create: `test/core/unit/test_md_os.py`

- [ ] **Step 1: Write failing unit tests for strict subheading writes and selective reads**

```python
@pytest.mark.core
def test_write_behavior_md_requires_subheading(tmp_path):
    file_path = tmp_path / "behavior.md"
    with pytest.raises(ValueError):
        write_behavior_md(file_path, "2026-04-18", "content", subheading=None)


@pytest.mark.core
def test_extract_behavior_md_reads_named_subheading_only():
    markdown = """
## 2026-04-18

### 日记总结
summary body

### 其他内容
other body
"""
    result = extract_behavior_md(markdown, "2026-04-18", subheading="日记总结")
    assert result["2026-04-18"] == "summary body"
```

- [ ] **Step 2: Run the new unit test file to confirm failure before refactor**

Run: `python -m pytest test/core/unit/test_md_os.py -v`
Expected: FAIL because the functions do not accept `subheading` yet.

- [ ] **Step 3: Refactor the markdown helpers to require `subheading` on writes and support `subheading="all"` on reads**

```python
def write_behavior_md(file_path, date, content, subheading: str, mode: str = "append") -> None:
    if not subheading:
        raise ValueError("write_behavior_md requires a non-empty subheading")
    ...


def extract_behavior_md(markdown_content, start_date, end_date=None, subheading: str = "all") -> Dict[str, str]:
    ...
```

- [ ] **Step 4: Re-export any changed function signatures from `lifeprism/llm/utils/__init__.py`**

```python
from .md_os import extract_behavior_logs_from_file, write_behavior_md
```

- [ ] **Step 5: Run the unit tests again**

Run: `python -m pytest test/core/unit/test_md_os.py -v`
Expected: PASS for required subheading, named subheading reads, and `all` reads.

- [ ] **Step 6: Commit**

```bash
git add lifeprism/llm/utils/md_os.py lifeprism/llm/utils/__init__.py test/core/unit/test_md_os.py
git commit -m "refactor(llm): structure behavior markdown by subheading"
```

### Task 3: Update summary generation logic to use external `outdate_summary` and hash writes

**Files:**
- Modify: `lifeprism/llm/function/diary_summary.py`
- Modify: `lifeprism/server/services/diary_service.py`
- Modify: `test/core/api/test_diary_ai_summary_api.py`

- [ ] **Step 1: Add a failing test that proves single-day regeneration still passes an existing summary into `ai_diary_summary` and updates `diary_source_hash`**

```python
def test_generate_diary_ai_summary_passes_existing_summary_to_llm(monkeypatch):
    captured = {}

    async def _fake_ai_diary_summary(date, mood, importance, custom_tags, outdate_summary=None):
        captured["outdate_summary"] = outdate_summary
        return {"content": "新总结"}

    ...
    assert captured["outdate_summary"] == "旧总结"
```

- [ ] **Step 2: Run the targeted test and verify it fails before the function signature is updated**

Run: `python -m pytest test/core/api/test_diary_ai_summary_api.py::test_generate_diary_ai_summary_passes_existing_summary_to_llm -v`
Expected: FAIL because `ai_diary_summary` still decides `outdate_summary` internally.

- [ ] **Step 3: Change `ai_diary_summary` to accept `outdate_summary` and keep create/update prompt branching unchanged**

```python
async def ai_diary_summary(date: str, mood: str, importence: str, custom_label: list[str], outdate_summary: str | None = None):
    ...
    sys_parts.append(update_summary_task_prompt if outdate_summary else create_summary_task_prompt)
    ...
    write_behavior_md(
        behavior_md_path,
        date,
        result,
        subheading="日记总结",
        mode="overwrite" if outdate_summary else "append",
    )
```

- [ ] **Step 4: Add a normalized-content hash helper in `diary_service.py` and use it only after summary generation succeeds**

```python
def _build_diary_source_hash(content: str) -> str:
    normalized = content.replace(" ", "").replace("\n", "")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
```

```python
success = diary_provider.update_diary(date, {
    "ai_summary": summary_content,
    "diary_source_hash": _build_diary_source_hash(content),
})
```

- [ ] **Step 5: Keep the existing single-day page behavior: if `item.get("ai_summary")` exists, pass it as `outdate_summary`; otherwise pass `None`**

```python
outdate_summary = item.get("ai_summary")
result = await ai_diary_summary(date, mood, importance, custom_tags, outdate_summary=outdate_summary)
```

- [ ] **Step 6: Run the single-day summary API tests**

Run: `python -m pytest test/core/api/test_diary_ai_summary_api.py -v`
Expected: PASS for empty-content rejection, overwrite semantics, old-summary passthrough, and hash persistence.

- [ ] **Step 7: Commit**

```bash
git add lifeprism/llm/function/diary_summary.py lifeprism/server/services/diary_service.py test/core/api/test_diary_ai_summary_api.py
git commit -m "feat(diary): persist summary source hash"
```

### Task 4: Add the backend range-update API with three existing-summary modes

**Files:**
- Modify: `lifeprism/server/schemas/diary_schemas.py`
- Modify: `lifeprism/server/services/diary_service.py`
- Modify: `lifeprism/server/api/diary_api.py`
- Create: `test/core/api/test_diary_ai_summary_range_api.py`

- [ ] **Step 1: Write failing API tests for the three range-update modes**

```python
@pytest.mark.core
def test_range_summary_mode_regenerate_all_updates_existing_summaries(monkeypatch):
    ...
    assert called_dates == ["2026-04-18", "2026-04-19"]


@pytest.mark.core
def test_range_summary_mode_regenerate_changed_only_updates_mismatched_hashes(monkeypatch):
    ...
    assert called_dates == ["2026-04-19"]


@pytest.mark.core
def test_range_summary_mode_skip_existing_only_creates_missing_summaries(monkeypatch):
    ...
    assert called_dates == ["2026-04-20"]
```

- [ ] **Step 2: Run the new range API test file to confirm it fails**

Run: `python -m pytest test/core/api/test_diary_ai_summary_range_api.py -v`
Expected: FAIL because the request schema, route, and service do not exist yet.

- [ ] **Step 3: Add request/response schemas for the range endpoint**

```python
class ExistingSummaryMode(str, Enum):
    REGENERATE_ALL = "regenerate_all"
    REGENERATE_CHANGED = "regenerate_changed"
    SKIP_EXISTING = "skip_existing"


class GenerateDiaryAISummaryRangeRequest(BaseModel):
    start_date: str
    end_date: str
    existing_summary_mode: ExistingSummaryMode


class GenerateDiaryAISummaryRangeResponse(BaseModel):
    created_dates: List[str] = Field(default=[])
    updated_dates: List[str] = Field(default=[])
    skipped_dates: List[str] = Field(default=[])
```

- [ ] **Step 4: Add a service function that filters by range and non-empty content, then applies the three strategies**

```python
async def generate_diary_ai_summary_range(request: GenerateDiaryAISummaryRangeRequest) -> GenerateDiaryAISummaryRangeResponse:
    ...
```

- [ ] **Step 5: Add the API route before `/{date}` dynamic routes to avoid path conflicts**

```python
@router.post("/ai_summary/range", response_model=GenerateDiaryAISummaryRangeResponse, summary="按日期范围更新日记 AI 总结")
async def generate_diary_ai_summary_range(request: GenerateDiaryAISummaryRangeRequest):
    return await diary_service.generate_diary_ai_summary_range(request)
```

- [ ] **Step 6: Run the new range API tests**

Run: `python -m pytest test/core/api/test_diary_ai_summary_range_api.py -v`
Expected: PASS for regenerate-all, regenerate-changed, and skip-existing modes.

- [ ] **Step 7: Commit**

```bash
git add lifeprism/server/schemas/diary_schemas.py lifeprism/server/services/diary_service.py lifeprism/server/api/diary_api.py test/core/api/test_diary_ai_summary_range_api.py
git commit -m "feat(diary): add range ai summary update api"
```

### Task 5: Add the journal settings entry and range update modal

**Files:**
- Modify: `frontend/apps/mindspace/components/journal/diaryTypes.ts`
- Modify: `frontend/apps/mindspace/components/journal/diaryApi.ts`
- Modify: `frontend/apps/mindspace/components/journal/SettingsPopover.tsx`
- Modify: `frontend/apps/mindspace/components/journal/journal.tsx`
- Create: `frontend/apps/mindspace/components/journal/RangeSummaryModal.tsx`

- [ ] **Step 1: Add failing frontend type usage for the new range request/response and modal mode options**

```ts
export type ExistingSummaryMode = 'regenerate_all' | 'regenerate_changed' | 'skip_existing';
```

- [ ] **Step 2: Run the frontend build to confirm the new symbols are missing**

Run: `Set-Location frontend; npm run build`
Expected: FAIL because the modal and range API types do not exist yet.

- [ ] **Step 3: Add the range API helper in `diaryApi.ts`**

```ts
async generateAiSummaryRange(data: GenerateDiaryAISummaryRangeRequest): Promise<GenerateDiaryAISummaryRangeResponse> {
  const res = await fetch(`${getApiBase()}/ai_summary/range`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  ...
}
```

- [ ] **Step 4: Add a new settings menu item and a dedicated modal component**

```tsx
<button
  onClick={() => { onSelectRangeSummary(); onClose(); }}
  className="w-full flex items-center gap-3 px-5 py-3.5 ..."
>
  范围更新总结
</button>
```

```tsx
<RangeSummaryModal
  open={showRangeSummaryModal}
  onClose={() => setShowRangeSummaryModal(false)}
  onSubmit={handleRangeSummarySubmit}
  initialDate={activeDate}
/>
```

- [ ] **Step 5: In `journal.tsx`, keep single-day regenerate unchanged and add a separate handler for range updates**

```tsx
const handleRangeSummarySubmit = useCallback(async (payload) => {
  const response = await DiaryAPI.generateAiSummaryRange(payload);
  toast.success(`已生成 ${response.created_dates.length} 条，更新 ${response.updated_dates.length} 条`);
  await loadDiary(activeDate);
}, [activeDate, loadDiary]);
```

- [ ] **Step 6: Use `toLocalDateString` for any Date -> request string conversion inside the modal**

```tsx
const startDate = toLocalDateString(start);
const endDate = toLocalDateString(end);
```

- [ ] **Step 7: Run the frontend build again**

Run: `Set-Location frontend; npm run build`
Expected: PASS with the new modal, settings item, and range update API types wired up.

- [ ] **Step 8: Commit**

```bash
git add frontend/apps/mindspace/components/journal/diaryTypes.ts frontend/apps/mindspace/components/journal/diaryApi.ts frontend/apps/mindspace/components/journal/SettingsPopover.tsx frontend/apps/mindspace/components/journal/journal.tsx frontend/apps/mindspace/components/journal/RangeSummaryModal.tsx
git commit -m "feat(mindspace): add range diary summary updater"
```

### Task 6: Sync formal docs and run end-to-end verification

**Files:**
- Modify: `docs/specs/2026-04-15-mind-space-diary.md`
- Modify: `docs/superpowers/plans/index.md`
- Test: `test/core/api/test_diary_ai_summary_api.py`
- Test: `test/core/api/test_diary_ai_summary_range_api.py`
- Test: `test/core/unit/test_md_os.py`

- [ ] **Step 1: Update the formal diary spec with `diary_source_hash`, the range update entry, and the new behavior.md write rule summary**

```md
- `diary_source_hash`: 当前 `ai_summary` 对应的正文 hash
- 设置按钮新增“范围更新 AI 总结”入口
- 范围更新支持：全部重生成 / 仅更新正文变化的已有摘要 / 跳过已有摘要
```

- [ ] **Step 2: Add this implementation plan to `docs/superpowers/plans/index.md`**

```md
| [2026-04-18-diary-range-ai-summary-implementation.md](2026-04-18-diary-range-ai-summary-implementation.md) | 日记范围手动总结实施计划，覆盖 hash 判定、behavior.md 次级标题、批量更新 API 和前端设置入口。 |
```

- [ ] **Step 3: Run all targeted backend tests**

Run: `python -m pytest test/core/api/test_diary_ai_summary_api.py test/core/api/test_diary_ai_summary_range_api.py test/core/unit/test_md_os.py -v`
Expected: PASS for single-day summary, range update modes, and markdown structure helpers.

- [ ] **Step 4: Run the frontend build**

Run: `Set-Location frontend; npm run build`
Expected: PASS with no TypeScript or Vite errors.

- [ ] **Step 5: Execute the manual verification flow**

```md
1. 打开 Mind Space 日记页面。
2. 从设置菜单进入“范围更新总结”。
3. 选择一段包含无 summary、已有 summary 且正文未变化、已有 summary 且正文已变化三类日期的范围。
4. 选择“重新生成全部内容”，确认已有 summary 的日期全部更新。
5. 选择“仅重新生成日记变化了的总结”，确认只有 hash 不一致的已有 summary 被更新。
6. 选择“不覆盖已有的总结”，确认只有无 summary 的日期首次生成。
7. 回到某个单日页面，点击现有“重新生成”，确认单日功能行为未变。
8. 检查 `behavior.md`，确认目标日期内容写在 `### 日记总结` 下。
```

- [ ] **Step 6: Commit**

```bash
git add docs/specs/2026-04-15-mind-space-diary.md docs/superpowers/plans/index.md
git commit -m "docs(diary): document range ai summary flow"
```

## Self-Review

### Spec coverage

- `diary_source_hash` 的语义、新增列和旧库迁移由 Task 1 覆盖。
- `behavior.md` 次级标题结构和 `md_os.py` 严格接口由 Task 2 覆盖。
- `ai_diary_summary` 的 `outdate_summary` 外部传入和单日行为保持不变由 Task 3 覆盖。
- 范围批量更新三种策略由 Task 4 覆盖。
- 设置入口、日期范围弹窗和前端请求链路由 Task 5 覆盖。
- 正式 spec 同步和最终验证由 Task 6 覆盖。

### Placeholder scan

- 计划中所有新增接口都给出了明确文件路径、请求名和命令。
- 没有使用 “稍后补充逻辑” 这类占位描述。
- 每个任务都以先写失败测试、再实现、再验证、再提交的顺序组织。

### Type consistency

- 后端批量模式统一使用 `ExistingSummaryMode`。
- 前端与后端的模式值统一为 `regenerate_all` / `regenerate_changed` / `skip_existing`。
- 批量接口路径统一为 `POST /api/v2/diary/ai_summary/range`。
