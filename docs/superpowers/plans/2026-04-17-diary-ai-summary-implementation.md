---
version: 1.0
created_at: 2026-04-17
updated_at: 2026-04-17
last_updated: 创建日记 AI 总结实施计划
abstract: 规划日记 AI 总结功能的实施步骤，覆盖后端 API、Service、前端只读卡片、手动验证和正式 spec 同步。
title: Diary AI Summary Implementation Plan
status: active
related_spec: docs/superpowers/specs/2026-04-17-diary-ai-summary-design.md
---

# Diary AI Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add manual AI summary generation to the diary view, persist the generated summary to `diary.ai_summary`, and show it in a read-only card under the tag bar.

**Architecture:** Keep diary summary generation as an explicit side-effect endpoint under the existing `/diary` router. The backend will validate diary content, call `ai_diary_summary`, and overwrite `diary.ai_summary`; the frontend will add an isolated summary-generation flow that does not interfere with the existing autosave pipeline.

**Tech Stack:** FastAPI, Pydantic, existing `diary_service`/`diary_provider`, React 19, TypeScript, fetch API, pytest, Vite build

---

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建实施计划 |

## File Structure

- Modify: `D:\desktop\软件开发\LifeWatch-AI\.worktrees\feat_lifeprism_tool_use\lifeprism\server\schemas\diary_schemas.py`
- Modify: `D:\desktop\软件开发\LifeWatch-AI\.worktrees\feat_lifeprism_tool_use\lifeprism\server\services\diary_service.py`
- Modify: `D:\desktop\软件开发\LifeWatch-AI\.worktrees\feat_lifeprism_tool_use\lifeprism\server\api\diary_api.py`
- Create: `D:\desktop\软件开发\LifeWatch-AI\.worktrees\feat_lifeprism_tool_use\test\core\api\test_diary_ai_summary_api.py`
- Modify: `D:\desktop\软件开发\LifeWatch-AI\.worktrees\feat_lifeprism_tool_use\frontend\apps\mindspace\components\journal\diaryTypes.ts`
- Modify: `D:\desktop\软件开发\LifeWatch-AI\.worktrees\feat_lifeprism_tool_use\frontend\apps\mindspace\components\journal\diaryApi.ts`
- Modify: `D:\desktop\软件开发\LifeWatch-AI\.worktrees\feat_lifeprism_tool_use\frontend\apps\mindspace\components\journal\journal.tsx`
- Modify: `D:\desktop\软件开发\LifeWatch-AI\.worktrees\feat_lifeprism_tool_use\docs\specs\2026-04-15-mind-space-diary.md`
- Modify: `D:\desktop\软件开发\LifeWatch-AI\.worktrees\feat_lifeprism_tool_use\docs\superpowers\plans\index.md`

### Responsibility Notes

- `diary_schemas.py` 定义 diary 专用 AI 总结响应模型，避免复用 report 的 token 响应结构。
- `diary_service.py` 持有内容读取、空日记校验、LLM 调用、数据库覆盖写入和枚举映射。
- `diary_api.py` 只负责新增 `POST /{date}/ai_summary` 路由和 HTTP 状态转换。
- `test/core/api/test_diary_ai_summary_api.py` 覆盖空日记、成功覆盖、失败不覆盖三个关键契约。
- `diaryApi.ts` 和 `journal.tsx` 持有前端独立的“生成 summary”请求与 UI 状态，不修改正文 autosave 时序。
- `2026-04-15-mind-space-diary.md` 将保留字段表述更新为已实现契约。

### Task 1: Add the backend response schema and API contract

**Files:**
- Modify: `lifeprism/server/schemas/diary_schemas.py`
- Modify: `lifeprism/server/api/diary_api.py`
- Test: `test/core/api/test_diary_ai_summary_api.py`

- [ ] **Step 1: Add the diary-specific AI summary response schema**

```python
from pydantic import BaseModel, Field


class DiaryAISummaryResponse(BaseModel):
    """日记 AI 总结响应"""
    content: str = Field(..., description="AI 生成的日记总结内容")
```

- [ ] **Step 2: Export the new schema from the diary schema module without changing existing diary item contracts**

```python
class SaveDiaryContentRequest(BaseModel):
    """保存日记内容"""
    content: str = Field(..., description="日记 md 内容")


class DiaryAISummaryResponse(BaseModel):
    """日记 AI 总结响应"""
    content: str = Field(..., description="AI 生成的日记总结内容")
```

- [ ] **Step 3: Add the new POST route under the existing diary CRUD section**

```python
@router.post("/{date}/ai_summary", response_model=DiaryAISummaryResponse, summary="生成日记 AI 总结")
async def generate_diary_ai_summary(
    date: str = Path(..., description="日期 YYYY-MM-DD"),
):
    try:
        return await diary_service.generate_diary_ai_summary(date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

- [ ] **Step 4: Keep route ordering safe by placing the new route after `/{date}` read/update routes and before no conflicting dynamic siblings**

```python
@router.put("/{date}/content", response_model=DiaryItem, summary="保存日记内容")
async def save_diary_content(...):
    ...


@router.post("/{date}/ai_summary", response_model=DiaryAISummaryResponse, summary="生成日记 AI 总结")
async def generate_diary_ai_summary(...):
    ...
```

- [ ] **Step 5: Write the failing API test skeleton for the empty-diary contract**

```python
import pytest
from fastapi.testclient import TestClient

from lifeprism.server.main import app


@pytest.mark.core
def test_generate_diary_ai_summary_rejects_empty_content(monkeypatch):
    client = TestClient(app)
    response = client.post("/api/v2/diary/2026-04-17/ai_summary")
    assert response.status_code == 400
    assert response.json()["detail"] == "日记为空，无法总结"
```

- [ ] **Step 6: Run the targeted test to verify it fails before service implementation**

Run: `python -m pytest test/core/api/test_diary_ai_summary_api.py::test_generate_diary_ai_summary_rejects_empty_content -v`
Expected: FAIL because the new route or service function does not exist yet.

- [ ] **Step 7: Commit**

```bash
git add lifeprism/server/schemas/diary_schemas.py lifeprism/server/api/diary_api.py test/core/api/test_diary_ai_summary_api.py
git commit -m "feat(diary): add ai summary api contract"
```

### Task 2: Implement the backend service flow with overwrite semantics

**Files:**
- Modify: `lifeprism/server/services/diary_service.py`
- Test: `test/core/api/test_diary_ai_summary_api.py`

- [ ] **Step 1: Add label-mapping helpers so LLM input uses readable Chinese labels**

```python
_MOOD_LABEL_MAP = {
    "very_happy": "非常愉悦",
    "happy": "有点开心",
    "calm": "平静",
    "bad": "不太好",
    "very_bad": "非常不好",
}

_IMPORTANCE_LABEL_MAP = {
    "important": "重要",
    "normal": "一般",
    "unimportant": "平凡",
}


def _map_diary_meta_for_summary(item: dict) -> tuple[Optional[str], Optional[str], list[str]]:
    mood = _MOOD_LABEL_MAP.get(item.get("mood")) if item.get("mood") else None
    importance = _IMPORTANCE_LABEL_MAP.get(item.get("importance")) if item.get("importance") else None
    custom_tags = _parse_custom_tags(item.get("custom_tags"))
    return mood, importance, custom_tags
```

- [ ] **Step 2: Add the async service function with empty-content validation**

```python
from lifeprism.llm.function.diary_summary import ai_diary_summary
from lifeprism.server.schemas.diary_schemas import DiaryAISummaryResponse


async def generate_diary_ai_summary(date: str) -> DiaryAISummaryResponse:
    item = diary_provider.get_diary_by_date(date)
    if not item:
        item = get_diary(date)
        if not item:
            raise ValueError(f"日记不存在: {date}")
        item = diary_provider.get_diary_by_date(date)

    content = _read_diary_content(date).strip()
    if not content:
        raise ValueError("日记为空，无法总结")

    mood, importance, custom_tags = _map_diary_meta_for_summary(item)
    result = await ai_diary_summary(date, mood, importance, custom_tags)
    summary_content = result["content"] if isinstance(result, dict) else getattr(result, "content", None)
    if not summary_content:
        raise ValueError("AI 总结生成失败")

    success = diary_provider.update_diary(date, {"ai_summary": summary_content})
    if not success:
        raise ValueError("AI 总结保存失败")

    return DiaryAISummaryResponse(content=summary_content)
```

- [ ] **Step 3: Add a success-path API test that proves the old summary is overwritten**

```python
@pytest.mark.core
def test_generate_diary_ai_summary_overwrites_existing_summary(monkeypatch):
    from lifeprism.server.providers.diary_provider import diary_provider

    stored = {
        "date": "2026-04-17",
        "mood": "calm",
        "importance": "normal",
        "custom_tags": '["阅读"]',
        "ai_summary": "旧总结",
        "created_at": "",
        "updated_at": "",
    }

    monkeypatch.setattr(diary_provider, "get_diary_by_date", lambda date: stored)
    monkeypatch.setattr("lifeprism.server.services.diary_service._read_diary_content", lambda date: "今天写了很多内容")
    monkeypatch.setattr("lifeprism.server.services.diary_service.ai_diary_summary", lambda *args, **kwargs: {"content": "新总结"})

    updated_payloads = []
    monkeypatch.setattr(diary_provider, "update_diary", lambda date, data: updated_payloads.append(data) or True)

    client = TestClient(app)
    response = client.post("/api/v2/diary/2026-04-17/ai_summary")
    assert response.status_code == 200
    assert response.json() == {"content": "新总结"}
    assert updated_payloads == [{"ai_summary": "新总结"}]
```

- [ ] **Step 4: Add a failure-path test that proves summary is not overwritten when the LLM call fails**

```python
@pytest.mark.core
def test_generate_diary_ai_summary_does_not_overwrite_on_llm_failure(monkeypatch):
    from lifeprism.server.providers.diary_provider import diary_provider

    stored = {
        "date": "2026-04-17",
        "mood": "calm",
        "importance": "normal",
        "custom_tags": "[]",
        "ai_summary": "旧总结",
        "created_at": "",
        "updated_at": "",
    }

    monkeypatch.setattr(diary_provider, "get_diary_by_date", lambda date: stored)
    monkeypatch.setattr("lifeprism.server.services.diary_service._read_diary_content", lambda date: "今天写了很多内容")

    async def _raise_failure(*args, **kwargs):
        raise RuntimeError("llm down")

    monkeypatch.setattr("lifeprism.server.services.diary_service.ai_diary_summary", _raise_failure)

    update_called = False

    def _update_diary(*args, **kwargs):
        nonlocal update_called
        update_called = True
        return True

    monkeypatch.setattr(diary_provider, "update_diary", _update_diary)

    client = TestClient(app)
    response = client.post("/api/v2/diary/2026-04-17/ai_summary")
    assert response.status_code == 500
    assert update_called is False
```

- [ ] **Step 5: Run the API test file and verify all backend contracts pass**

Run: `python -m pytest test/core/api/test_diary_ai_summary_api.py -v`
Expected: PASS for empty-content, overwrite, and no-overwrite-on-failure cases.

- [ ] **Step 6: Commit**

```bash
git add lifeprism/server/services/diary_service.py test/core/api/test_diary_ai_summary_api.py
git commit -m "feat(diary): implement ai summary service flow"
```

### Task 3: Add the frontend API and diary summary card state

**Files:**
- Modify: `frontend/apps/mindspace/components/journal/diaryTypes.ts`
- Modify: `frontend/apps/mindspace/components/journal/diaryApi.ts`
- Modify: `frontend/apps/mindspace/components/journal/journal.tsx`

- [ ] **Step 1: Add the frontend response type for diary AI summary**

```ts
export interface DiaryAISummaryResponse {
  content: string;
}
```

- [ ] **Step 2: Add the new fetch helper in `diaryApi.ts`**

```ts
import type {
  DiaryItem,
  DiaryMetaItem,
  DiaryAISummaryResponse,
  UpdateDiaryMetaRequest,
  SaveDiaryContentRequest,
  TemplateItem,
} from './diaryTypes';

async generateAiSummary(date: string): Promise<DiaryAISummaryResponse> {
  const res = await fetch(`${getApiBase()}/${date}/ai_summary`, {
    method: 'POST',
  });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(errorText || `生成日记 AI 总结失败: ${res.statusText}`);
  }
  return res.json();
},
```

- [ ] **Step 3: Add dedicated UI state in `journal.tsx` without mixing it into autosave state**

```tsx
const [isGeneratingSummary, setIsGeneratingSummary] = useState(false);

const handleGenerateSummary = useCallback(async () => {
  const dateStr = formatDate(activeDate);
  if (!content.trim()) {
    toast.info('日记为空，无法总结');
    return;
  }

  try {
    setIsGeneratingSummary(true);
    const response = await DiaryAPI.generateAiSummary(dateStr);
    setDiary(prev => prev ? { ...prev, ai_summary: response.content } : prev);
    toast.success('AI 总结已生成');
  } catch (e) {
    console.error('生成日记 AI 总结失败:', e);
    toast.error('AI 总结生成失败');
  } finally {
    setIsGeneratingSummary(false);
  }
}, [activeDate, content]);
```

- [ ] **Step 4: Render the summary card between `DiaryTagBar` and the markdown editor**

```tsx
<div className="mt-5 rounded-[24px] border border-black/10 bg-white/55 backdrop-blur-xl px-5 py-4 shadow-[0_18px_40px_-24px_rgba(0,0,0,0.28)]">
  <div className="mb-3 flex items-center justify-between gap-4">
    <button
      onClick={handleGenerateSummary}
      disabled={isGeneratingSummary}
      className="rounded-full bg-slate-800 px-4 py-2 text-xs font-semibold tracking-[0.22em] text-white transition disabled:cursor-not-allowed disabled:opacity-60"
    >
      {isGeneratingSummary ? '生成中' : 'AI 总结'}
    </button>
    <span className="text-[10px] uppercase tracking-[0.28em] text-slate-400">只读</span>
  </div>
  <div className="whitespace-pre-wrap text-[15px] leading-8 text-slate-700">
    {diary?.ai_summary || '暂无 AI 总结，点击左上角按钮生成'}
  </div>
</div>
```

- [ ] **Step 5: Run the frontend build to verify the new types and JSX compile**

Run: `Set-Location frontend; npm run build`
Expected: Vite build succeeds with no TypeScript errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/apps/mindspace/components/journal/diaryTypes.ts frontend/apps/mindspace/components/journal/diaryApi.ts frontend/apps/mindspace/components/journal/journal.tsx
git commit -m "feat(mindspace): show diary ai summary card"
```

### Task 4: Update the formal diary spec and plan navigation

**Files:**
- Modify: `docs/specs/2026-04-15-mind-space-diary.md`
- Modify: `docs/superpowers/plans/index.md`
- Modify: `docs/superpowers/plans/2026-04-17-diary-ai-summary-implementation.md`

- [ ] **Step 1: Update the formal diary spec so AI summary is no longer marked as unimplemented**

```md
本 spec 覆盖：
1. 日记的存储机制（文件 + 数据库混合存储）
2. 日记 CRUD API 契约
3. 日记 AI 总结手动生成 API 契约
4. 模板管理 API 契约
```

- [ ] **Step 2: Add the new API line to the diary route table**

```md
| `POST` | `/diary/{date}/ai_summary` | 手动生成指定日期日记 AI 总结，成功后覆盖 `ai_summary` | - | `{ content: string }` |
```

- [ ] **Step 3: Add the AI summary card to the interaction notes**

```md
**AI 总结卡片**
- 位置：标签栏下方，编辑器上方
- 内容：显示 `ai_summary` 或空状态提示
- 按钮：左上角 `AI 总结`，手动触发生成
- 限制：只读，不可编辑，高度随内容自然撑开
```

- [ ] **Step 4: Update the superpowers plan index with the new plan entry**

```md
| [2026-04-17-diary-ai-summary-implementation.md](2026-04-17-diary-ai-summary-implementation.md) | 日记 AI 总结实施计划，覆盖 diary API、Service、前端只读卡片、验证和正式 spec 同步。 |
```

- [ ] **Step 5: Run a docs sanity check for placeholder text**

Run: `Select-String -Path docs/specs/2026-04-15-mind-space-diary.md,docs/superpowers/plans/index.md -Pattern 'T[O]DO|TB[D]|占位|implement[ ]later$'`
Expected: no output related to the new AI summary sections.

- [ ] **Step 6: Commit**

```bash
git add docs/specs/2026-04-15-mind-space-diary.md docs/superpowers/plans/index.md docs/superpowers/plans/2026-04-17-diary-ai-summary-implementation.md
git commit -m "docs(diary): update ai summary specs and plan index"
```

### Task 5: Run end-to-end verification and prepare handoff

**Files:**
- Test: `test/core/api/test_diary_ai_summary_api.py`
- Test: `frontend/apps/mindspace/components/journal/journal.tsx`
- Modify: `docs/temp/temp_lecture_record/temp_lecture_record.md` (only if implementation feedback reveals a new lesson)

- [ ] **Step 1: Run the backend API tests one more time from the repo root**

Run: `python -m pytest test/core/api/test_diary_ai_summary_api.py -v`
Expected: PASS with the three AI summary API contracts green.

- [ ] **Step 2: Run the frontend build again from the frontend directory**

Run: `Set-Location frontend; npm run build`
Expected: build completes successfully.

- [ ] **Step 3: Execute the manual journal verification flow**

```md
1. 打开 Mind Space 日记页面。
2. 选择一个已有正文且 `ai_summary` 为空的日期。
3. 确认标签栏下方出现“暂无 AI 总结，点击左上角按钮生成”。
4. 点击 `AI 总结` 按钮，确认按钮进入 disabled/loading 状态。
5. 生成成功后确认卡片更新为新 summary，且编辑器内容未被改动。
6. 选择一个正文为空的日期，点击 `AI 总结`，确认前端提示“日记为空，无法总结”。
7. 切回有旧 summary 的日期再次生成，确认内容被新 summary 覆盖。
```

- [ ] **Step 4: Record any new implementation lesson only if a real mistake happened during execution**

```md
仅在执行过程中出现新的、被纠正的错误时，追加到 `docs/temp/temp_lecture_record/temp_lecture_record.md`。
如果没有新的纠正事件，这一步跳过，不为了凑步骤而写入。
```

- [ ] **Step 5: Commit**

```bash
git add test/core/api/test_diary_ai_summary_api.py frontend/apps/mindspace/components/journal/journal.tsx
git commit -m "test(diary): verify ai summary flow"
```

## Self-Review

### Spec coverage

- 独立 `POST /diary/{date}/ai_summary` 契约由 Task 1 覆盖。
- 空日记 `400`、成功覆盖和失败不覆盖由 Task 2 的 API 测试覆盖。
- 前端只读卡片、按钮 loading、空状态和成功更新 UI 由 Task 3 覆盖。
- 正式 spec 同步由 Task 4 覆盖。
- 最终验证和手动回归由 Task 5 覆盖。

### Placeholder scan

- 计划正文没有使用未定义占位步骤。
- 每个代码步骤都给了明确片段或命令。
- 手动验证步骤写成了可执行清单，没有抽象描述。

### Type consistency

- 后端统一使用 `DiaryAISummaryResponse` 作为新响应名。
- 前端统一使用 `generateAiSummary` 作为 API 方法名。
- API 路径统一为 `POST /api/v2/diary/{date}/ai_summary`。
