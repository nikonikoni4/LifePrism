# Repository 重构向后兼容检查清单

## 概述

本文档记录 `lifeprism/repository/__init__.py` 中所有 repository 的检查状态，确保重构过程中的向后兼容性。

## Repository 列表

### Provider 层（单表数据访问）

- [x] diary_repository
- [x] todo_repository 
- [x] timeline_repository
- [x] tokens_usage_repository
- [x] raw_behavior_analysis_repository
- [x] behavior_analysis_repository
- [x] screen_capture_repository

### Aggregator 层（多表数据聚合）

- [x] habit_repository
- [x] mood_repository
- [x] goal_repository
- [x] habit_chain_repository
- [x] category_repository
- [x] map_cache_repository
- [x] plan_doc_repository

## 检查方法

### 步骤 1：确定对比对象

**优先级顺序**：
1. 如果存在独立的 `xx_provider.py` 文件在 `lifeprism/server/providers/` 下，以该文件作为对比对象
2. 如果不存在独立文件，检查 `lifeprism/server/providers/statistical_data_providers.py` 中是否包含相关表的操作
3. 如果以上都没有，直接搜索项目中使用相关表名的代码，找到原始实现位置

**搜索范围**：
- 只能在`lifeprism/server`下进行搜索


### 步骤 2：对比方法差异

对比 repository（重构后）与原 provider（旧实现）的方法列表：

```
原 provider 方法列表：
- method_a()
- method_b()
- method_c()

repository 方法列表：
- method_a() ✅
- method_c() ❌ 缺失

缺失方法：
- method_b()
```

### 步骤 3：验证方法是否仍在使用

搜索方法在项目中的实际调用情况：

```bash
# 使用 Grep 工具搜索
pattern: method_b
path: d:\desktop\软件开发\LifeWatch-AI
output_mode: content
```

**判断标准**：
- 在 `lifeprism/server/` 下的调用 → **仍在使用**，需要添加
- 仅在 `lifeprism/repository/` 下的调用 → 检查是否为测试代码
- 搜索结果为空 → 可以暂时不处理

### 步骤 4：添加缺失方法到 Repository

**对于 Provider 类型的 Repository**：
直接在 repository 中添加缺失的方法实现

**对于 Aggregator 类型的 Repository**：
- 首先检查其内部的 `self.provider` 是否已具备该方法
- 如果 provider 已有 → 直接透传（推荐）
- 如果 provider 没有 → 在 aggregator 中直接实现

### 步骤 5：Aggregator 特殊处理

Aggregator 类型的 repository 需要额外检查：

```
aggregator 内部结构：
├── self.provider (TodoProvider)
│   ├── get_todos_by_date()
│   ├── get_todo_by_id()
│   └── ...
│
└── 透传方法列表
    ├── get_child_todos() → provider.get_child_todos()
    └── delete_todo_cascade() → provider.delete_todo_cascade()
```

**透传原则**：
- 如果 `self.provider` 已实现该方法 → 在 aggregator 中透传
- 如果 `self.provider` 没有该方法 → 在 aggregator 中直接实现或要求 provider 添加

---

## 检查说明

每个 repository 需要检查以下方面：

1. **方法完整性**：所有原有方法是否已透传
2. **参数一致性**：方法签名是否与重构前保持一致
3. **返回值类型**：返回值类型是否与重构前一致
4. **异常处理**：异常类型是否与重构前一致
5. **调用方验证**：确认所有调用方已更新或兼容

## 更新记录

| 日期 | Repository | 操作 | 说明 |
|------|-----------|------|------|
| 2026-04-28 | todo_repository | 添加透传方法 | 新增5个方法的透传 |
| 2026-04-28 | 全部13个repository | 向后兼容性检查 | 完成所有repository的检查 |
| 2026-04-28 | goal_repository | 添加透传方法 | 新增3个方法的透传（get_goals_linked_to_category, get_stat_by_date, upsert_stat） |

## 检查结果汇总

### Provider 层（6个）
- ✅ diary_repository: 完全兼容
- ✅ timeline_repository: 完全兼容
- ✅ tokens_usage_repository: 架构升级（聚合逻辑上移到service层）
- ✅ raw_behavior_analysis_repository: 新增表
- ✅ behavior_analysis_repository: 新增表
- ✅ screen_capture_repository: 新增表

### Aggregator 层（7个）
- ✅ habit_repository: 完全兼容
- ✅ mood_repository: 完全兼容
- ✅ goal_repository: 已添加3个透传方法
- ✅ habit_chain_repository: 完全兼容
- ✅ category_repository: 职责不同（颜色管理服务）
- ✅ map_cache_repository: 缺失方法为遗留代码（未使用）
- ✅ plan_doc_repository: 完全兼容
