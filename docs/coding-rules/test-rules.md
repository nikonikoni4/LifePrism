---
version: 1.0
created_at: 2026-04-15
updated_at: 2026-04-15
last_updated: 初始版本
abstract: 测试编写指南，定义测试目录结构（core/debug/regression/scenarios）、测试分类决策流程、数据来源选择、验证方法（断言/快照/业务场景）和测试标记规范
---

# 测试编写指南

## 测试目录结构

```
test/
├───core                        # 针对于代码正确性的测试
│   ├───api                         # API 测试
│   ├───integration                 # 集成测试
│   └───unit                        # 单元测试
├───debug                       # 调试测试（临时，用完即删）
├───manual                      # 人工测试文档
├───regression                  # 回归测试（复现bug，避免已经出现的bug再次出现）
├───scenarios                   # 业务场景专项测试
│   └───docs                        # 业务场景文档
│   └───test                        # 业务场景测试
├───testdata                    # 测试数据集合
├── __snapshots__/              # 快照文件（自动生成）
```

## 规则1：测试写在哪

### 决策流程

```
这是什么类型的测试？
├─ 专项业务场景测试 -> scenarios
├─ 临时调试 → debug/ (用完即删)
├─ 修复 bug → regression/ (关联 issue)
└─ 核心功能 → core/
    ├─ 无外部依赖 → core/unit/{module}/
    ├─ 多模块协作 → core/integration/
    └─ HTTP 端点 → core/api/
```

### 判断标准

| 测试类型 | 目录 | 何时使用 |
|---------|------|---------|
| 单元测试 | `core/unit/{module}/` | 纯函数、工具类、配置解析（无数据库/网络/文件） |
| 集成测试 | `core/integration/` | 跨模块协作、数据库、LLM、文件系统 |
| API 测试 | `core/api/` | FastAPI 路由、请求/响应验证 |
| 回归测试 | `regression/` | bug 出现后编写复现测试 |
| 业务场景测试 | `scenarios/` | 针对与专门的业务场景进行测试  |
| 调试测试 | `debug/` | 临时调试，用完即删 |

### 命名规范

1. 对于测试脚本命名规范：test_<测试内容>.py
2. 对于业务场景测试文档(test)：scenarios_<测试业务>.md 

## 规则2：数据从哪来

### 数据来源选择

1. **验证程序正确性测试**（单元测试，部分api和部分集成测试）：可以直接在脚本中直接编写数据
2. **需要真实数据环境的测试**：使用`test/testdata`，包含数据库以及各种文档类数据
3. **特定业务场景的测试**：依据所编写的业务场景文档自行在脚本中编写数据

## 规则3：如何验证

1. **简单可直接明确结果的测试**：使用断言，类型判断等方法直接进行验证
1. **复杂不可使用预测结果的测试**：使用类型判断等方法进行验证，需要注意**输出必须在合理范围之内**
1. **需要保证程序输出不偏移的测试（比如数据清洗）**：使用快照、
1. **具有明确结果的业务场景的测试**：依据所编写的业务场景文档使用断言，类型判断等方式验证

### 业务场景验证示例

```python
# tests/core/integration/test_health_analysis.py
def test_high_heart_rate_analysis():
    """场景：心率异常用户的健康分析
    
    参考：tests/scenarios/health_analysis/high_heart_rate.md
    """
    # 从 testdata 或 database 获取数据
    user_data = load_test_data("user_data/high_heart_rate.json")
    
    # 执行业务逻辑
    result = llm.generate_health_analysis(user_data)
    
    # 根据场景描述验证关键信息
    assert "心率异常" in result
    assert "建议就医" in result
    assert "⚠️" in result
```

### 快照验证示例

```python
def test_generate_config(snapshot):
    config = generate_yaml_config(settings)
    assert config == snapshot
```

### 断言验证示例

```python
def test_calculate_bmi():
    bmi = calculate_bmi(weight=70, height=1.75)
    assert bmi == 22.86
```

## 规则4：测试标记

| 测试类型 | 必须标记 |
|---------|---------|
| core/ | `@pytest.mark.core` |
| regression/ | `@pytest.mark.regression`|
| debug/ | `@pytest.mark.debug` |
| scenarios/ | `@pytest.mark.scenarios`|
---


## 核心规则
<rules>
1. 必须先编写业务测试场景文档在`test/scenarios/docs/*.md`，在编写业务测试脚本`test/scenarios/test/*.md`

</rules>
