# Test 模块架构

## 一、目录结构

```
test/
├── README.md                    # 本文档：测试架构说明
├── database/                    # 测试数据库
│   ├── test.db                 # SQLite 测试数据库
│   ├── README.md               # 数据库说明文档
│   └── seed_data.sql           # 初始化数据脚本
├── scenarios/                   # 测试场景文档
│   ├── index.md                # 场景索引
│   └── {module}/               # 按功能模块组织
│       └── {scenario}.md       # 具体场景文档
├── fixtures/                    # 跨模块共享的静态测试数据（JSON/YAML）
├── factories/                   # 测试数据工厂函数（动态生成）
├── {module}/                    # 模块测试目录
│   ├── fixtures/               # 模块级静态数据、契约数据
│   ├── unit/                   # 单元测试
│   ├── integration/            # 集成测试
│   ├── api/                    # API 测试
│   └── contracts/              # 契约测试
├── e2e/                        # E2E 测试
└── manual/                      # 手动测试文档
    ├── index.md                # 手动测试索引
    └── {test-name}.md          # 手动测试步骤
```

---

## 二、模块职责说明

### 2.1 database/（测试数据库）

**职责**：提供可复用的测试数据库

**内容**：
- `test.db`：SQLite 测试数据库，包含预置的测试数据
- `README.md`：说明当前已有什么数据、AI 可以添加什么数据
- `seed_data.sql`：数据库初始化脚本

**使用场景**：
- 集成测试（高耦合）
- API 测试
- E2E 测试

**详细说明**：见 `database/README.md`

---

### 2.2 scenarios/（测试场景文档）

**职责**：定义业务测试场景，包含输入数据、预期结果、是否可自动化

**内容**：
- `index.md`：所有测试场景的索引
- `{module}/{scenario}.md`：具体场景文档

**场景文档包含**：
- 场景描述
- 测试数据（输入数据 + 数据特征）
- 预期结果
- 自动化测试（是否可自动化 + 测试脚本路径）
- 手动验证（是否需要手动验证 + 验证文档路径）

**使用场景**：
- AI 编写测试脚本的参考
- 手动测试的指导文档

**详细说明**：见 `scenarios/index.md`

---

### 2.3 fixtures/（跨模块共享静态数据）

**职责**：存放跨模块共享的静态测试数据

**内容**：
- JSON/YAML 格式的测试数据
- 例如：通用的用户数据、分类数据、配置数据

**使用场景**：
- 多个模块需要相同的测试数据
- 数据结构固定，不需要动态生成

**示例**：
```
fixtures/
├── users.json          # 通用用户数据
├── categories.json     # 通用分类数据
└── config.yaml         # 测试配置
```

---

### 2.4 factories/（测试数据工厂）

**职责**：提供动态生成测试数据的工厂函数

**内容**：
- Python 函数，用于生成测试数据
- 支持参数化，灵活生成不同场景的数据

**使用场景**：
- 需要动态生成测试数据
- 需要生成大量测试数据
- 数据结构复杂，需要编程生成

**示例**：
```python
# factories/activity_factory.py

def create_activity_event(
    user_id=1,
    timestamp=None,
    app_name="Chrome",
    duration=60
):
    """生成活动事件数据"""
    return {
        "user_id": user_id,
        "timestamp": timestamp or datetime.now(),
        "app_name": app_name,
        "duration": duration
    }
```

---

### 2.5 {module}/（模块测试目录）

**职责**：存放特定模块的测试代码

**结构**：
```
{module}/
├── fixtures/              # 模块级静态数据、契约数据
├── unit/                  # 单元测试
├── integration/           # 集成测试
├── api/                   # API 测试
└── contracts/             # 契约测试
```

**说明**：
- 后端测试采用集中管理
- 单元测试和契约测试通常是程序正确性测试
- API 测试和 E2E 测试通常是业务逻辑测试
- 集成测试可能包含两种类型

---

### 2.6 e2e/（端到端测试）

**职责**：验证完整的用户流程

**内容**：
- 端到端测试脚本
- 涉及前端 + 后端 + 数据库的完整流程

**使用场景**：
- 验证关键业务流程
- 回归测试

---

### 2.7 manual/（手动测试文档）

**职责**：存放无法自动化的测试文档（主要是 UI 交互测试）

**内容**：
- `index.md`：手动测试索引
- `{test-name}.md`：具体的手动测试步骤

**使用场景**：
- UI 交互测试
- 视觉效果验证
- 用户体验测试

---

## 三、测试类型与策略

| 测试类型           | 目的            | 数据来源                  | 依赖处理                   | 位置 |
| ------------------ | --------------- | ------------------------- | -------------------------- | ---- |
| 单元测试           | 验证单个函数/类 | Factories 或 就近定义     | Mock 所有外部依赖          | `{module}/unit/` |
| 集成测试（低耦合） | 验证模块间接口  | 模块契约数据 + Mock       | Mock 外部模块              | `{module}/integration/` |
| 集成测试（高耦合） | 验证真实协作    | 全局 fixtures + Factories | 测试数据库                 | `{module}/integration/` |
| API 测试           | 验证 HTTP 接口  | 模块 fixtures             | 测试数据库 + Mock 外部 API | `{module}/api/` |
| 契约测试           | 验证响应格式    | Schema 定义               | Mock 或 真实响应           | `{module}/contracts/` |
| E2E 测试           | 验证完整流程    | Seed 数据                 | 真实环境                   | `e2e/` |

---

## 四、测试数据管理

### 4.1 数据来源优先级

1. **就近定义** - 测试代码中直接定义（单元测试）
2. **Factories** - 动态生成（需要灵活性）
3. **模块 fixtures** - 模块级静态数据（模块特定）
4. **全局 fixtures** - 跨模块共享静态数据（通用数据）
5. **测试数据库** - 预置数据库（集成测试、API 测试、E2E 测试）

### 4.2 数据管理原则

- **单元测试**：优先就近定义或使用 Factories，避免依赖外部数据
- **集成测试**：根据耦合度选择 Mock 或测试数据库
- **API 测试**：使用测试数据库 + 模块 fixtures
- **E2E 测试**：使用测试数据库的 Seed 数据

---

## 五、测试场景文档规范

### 5.1 场景文档模板

```markdown
# 测试场景：{场景名称}

## 场景描述

简要描述测试场景的目的和背景。

## 测试数据

### 输入数据
- 数据来源：test/database/test.db 或 test/fixtures/xxx.json
- 关键参数：列出关键输入参数

### 数据特征
- 描述数据的特征（例如：数据量、覆盖范围、特殊情况）

## 预期结果

### 输出数据
- 描述预期的输出结果
- 列出关键验证点

## 自动化测试

✅ **可自动化** / ❌ **不可自动化**

测试脚本：`test/{module}/{type}/test_xxx.py::test_xxx`

验证点：
- [ ] 验证点 1
- [ ] 验证点 2

## 手动验证

✅ **需要手动验证** / ❌ **不需要**

验证文档：`test/manual/xxx.md`
```

### 5.2 自动化判断标准

**可自动化**：
- 纯后端逻辑
- API 接口调用
- 数据库查询结果
- 数据格式验证

**不可自动化**（需要手动验证）：
- UI 交互
- 视觉效果
- 用户体验
- 浏览器兼容性

---

## 六、AI 使用指南

### 6.1 编写测试时

1. **读取测试场景文档**：`test/scenarios/{module}/{scenario}.md`
2. **了解可用数据**：`test/database/README.md`
3. **选择测试类型**：根据测试目的选择单元/集成/API/契约/E2E
4. **选择数据来源**：根据测试类型选择合适的数据来源
5. **编写测试脚本**：
   - 可自动化 → `test/{module}/{type}/test_xxx.py`
   - 不可自动化 → `test/manual/xxx.md`

### 6.2 添加测试数据时

1. **检查是否允许添加**：`test/database/README.md`
2. **选择数据存放位置**：
   - 跨模块共享 → `test/fixtures/`
   - 模块特定 → `test/{module}/fixtures/`
   - 动态生成 → `test/factories/`
   - 数据库数据 → `test/database/seed_data.sql`
3. **更新文档**：更新相应的 README 或索引文件

---

## 七、测试运行

### 7.1 运行所有测试

```bash
pytest test/
```

### 7.2 运行特定模块测试

```bash
pytest test/lifeprism/
```

### 7.3 运行特定类型测试

```bash
# 单元测试
pytest test/ -m unit

# 集成测试
pytest test/ -m integration

# API 测试
pytest test/ -m api

# E2E 测试
pytest test/e2e/
```

### 7.4 初始化测试数据库

```bash
python test/database/seed_data.py
```

---

## 八、测试覆盖率

测试覆盖率报告自动生成到：`docs/generated/test-coverage.md`

查看覆盖率：
```bash
pytest --cov=lifeprism --cov-report=html
```

---

## 九、参考文档

- 测试数据库说明：`test/database/README.md`
- 测试场景索引：`test/scenarios/index.md`
- 手动测试索引：`test/manual/index.md`
