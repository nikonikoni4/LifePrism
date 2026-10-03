# deprecated_agent（已弃用的 agent 内核）

> **仅历史参考，不可作为运行内核。** 本目录不参与生产运行，不要在新代码中 import。

## 状态

- 2026-10-03 由 `lifeprism/llm/agent` 整体改名归档；`loop.py`、`context.py`、`tools/`、
  `skill.py`、`subagent.py` 源文件未删除、未改逻辑。
- 包内 import 已改写为 `lifeprism.llm.deprecated_agent.*`，仅保证历史代码可独立导入，
  不代表可用或受支持。
- `test/` 下对旧实现的引用同步指向本目录，这些测试是旧内核的历史回归，
  不代表新内核验收。

## 新实现位置

| 关注点 | 新实现 |
|--------|--------|
| agent 运行时内核（worker / service / provider / limiter / skills / prompts） | `lifeprism/llm/runtime/` |
| 生产业务工具（filesystem / lifeprismsystem / habit / custom_records / web） | `lifeprism/llm/runtime_tools/` |

## 不要做的事

- 不要新增对本目录的 import。
- 不要在本目录继续修 bug；问题应在新实现中处理。
- 不要以本目录代码作为新内核的验收基线。
