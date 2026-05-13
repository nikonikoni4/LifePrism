---
version: 1.0
created_at: 2026-05-13
updated_at: 2026-05-13
last_updated: 创建 LLM 测试框架规格初稿
abstract: LLM 测试框架规格，定义测试数据目录结构、输出目录结构、metadata 文件结构及测试基类抽象函数规范
id: llm-test-spec
title: LLM 测试框架规格
status: draft
module: llm-test
sourc_spec: test/llm_prompt_test.py/llm_test_base.py
related_plan:
code_scope: test/llm_prompt_test.py/llm_test_base.py
contract_refs: test/llm_prompt_test.py/llm_test_base.py
---

# LLM 测试框架规格

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建 spec 初稿 |
| 1.1 | 添加 set_temperature、set_prompt_version 方法 |

## Overview

LLM 测试框架用于对 LLM Prompt 进行系统化测试，支持多轮次测试、人工评估和结果追踪。框架采用基类抽象设计，具体测试逻辑由子类实现。

## Scope

- 测试数据输入管理
- 测试结果输出管理
- 测试元数据记录
- 人工评估表生成与读取

## Core Behavior

### 测试流程

1. 初始化测试实例（指定 prompt、版本、输入路径、输出路径、temperature）
2. 执行测试（可指定输入文件或默认全量测试）
3. 生成 Excel 评估表供人工审核
4. 人工在 Excel 中填写评估结果（通过/不通过、评分、原因）
5. 读取评估结果，计算通过率
6. 更新 metadata 记录

### 测试轮次

- 同一输入数据和 prompt 版本可进行多轮测试
- 每轮测试可指定不同的输入文件集合
- 默认全量测试输入文件夹中的所有文件

## Technical Contract

### 1. 测试数据目录结构

```
input_path/
├── {prompt_name}/          # 按 prompt 分组
│   ├── file1.md            # 输入文件（格式由具体测试决定）
│   ├── file2.md
│   └── ...
└── ...
```

**规则：**
- 输入文件格式由具体测试决定，框架只管理路径
- 一个文件夹放置一个 prompt 的输入内容
- 支持指定单个或多个输入文件进行部分测试

### 2. 输出目录结构

```
output_path/
├── {prompt_name}/                     # 按 prompt 名称分组
│   ├── meta_data.json                 # 测试元数据文件
│   └── {version}/                     # 按版本分组
│       ├── r{round}-t{temperature}.xlsx  # 评估表文件
│       └── ...
└── ...
```

**规则：**
- output_path 为该 prompt 的总输出地址
- 每个版本独立目录
- 评估表文件命名格式：`r{round}-t{temperature}.xlsx`
- 评估表 Sheet 名称：`r{round}-t{temperature}`

### 3. meta_data.json 文件结构

```json
[
  {
    "version": "v1",
    "round": "r1",
    "pass_ratio": 0.85,
    "temperature": 0.7,
    "create_at": "2026-05-13T10:30:00",
    "input_file": ["file1.md", "file2.md"]
  }
]
```

**字段说明：**

| 字段 | 类型 | 说明 |
| ---- | ---- | ---- |
| version | string | Prompt 版本号 |
| round | string | 测试轮次标识 |
| pass_ratio | float | 通过率（0-1） |
| temperature | float | LLM 温度参数 |
| create_at | string | 测试创建时间（ISO 8601 格式） |
| input_file | list[string] | 本轮测试的输入文件列表 |

### 4. 评估表结构

Excel 评估表包含 6 列：

| 列名 | 说明 |
| ---- | ---- |
| llm_input | LLM 输入内容 |
| llm_output | LLM 输出内容 |
| pass | 是否通过（人工填写） |
| score | 评分（人工填写） |
| reason | 原因说明（人工填写） |
| other | 其他备注（人工填写） |

### 5. LLMTestBase 抽象函数规范

#### 子类必须实现的抽象函数

| 函数 | 输入 | 输出 | 说明 |
| ---- | ---- | ---- | ---- |
| data_input | input_files: list[str] = None | list[Any] | 解析输入数据，返回 LLM 调用所需的数据列表 |
| run_test | input_files: list[str] = None | list[dict] | 执行测试，返回包含 llm_input 和 llm_output 的结果列表 |
| generate_eval_sheet | test_results: list[dict], round: str, temperature: float | Path | 生成 Excel 评估表，返回文件路径 |
| read_eval_result | eval_sheet_path: Path | float | 读取评估结果，计算并返回通过率（0-1） |

#### 基类提供的通用函数

| 函数 | 说明 |
| ---- | ---- |
| get_metadata | 获取 metadata 列表，不存在则自动创建 |
| save_metadata | 保存 metadata 到文件 |
| update_metadata | 更新 metadata（自动记录 create_at） |
| set_prompt_version | 设置 prompt 版本号 |
| set_temperature | 设置 temperature 参数 |

### 6. 设计约束

- 输入数据格式由具体测试决定，框架只管理路径
- LLM 调用通过 lifeprism.llm.providers.llm_providers.build_llm_client 统一接口
- 并发执行使用 asyncio.gather
- 评估在 Excel 中手动完成，系统读取结果自动更新 metadata

## Acceptance Notes

1. 框架能正确读取和写入 meta_data.json
2. 评估表能正确生成并包含 6 列结构
3. 子类实现的抽象函数能正确执行测试流程
4. 多轮次测试能正确记录和追踪

## Out of Spec

- 具体的 LLM 调用逻辑（由子类实现）
- 输入数据预处理逻辑（由子类实现）
- 评估表的具体样式和格式细节
- 测试结果的自动汇总报告
- 断点续测功能
- 测试并发控制策略
