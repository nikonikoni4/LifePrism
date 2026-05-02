---
version: 1.1
created_at: 2026-04-09
updated_at: 2026-04-10
last_updated: 补充 abstract 字段
abstract: 项目架构地图，概述仓库物理结构、抽象分层、前后端架构、主干数据流和关键依赖方向。
---

# ARCHITECTURE

> 面向第一次进入项目的人或 AI，快速说明 LifePrism 的整体结构、主干数据流和关键依赖边界。

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建架构地图初稿 |
| 1.1 | 补充 abstract 字段 |

## Overview

LifePrism 是一个围绕个人成长构建的桌面应用项目，核心目标是把行为数据、目标管理、习惯养成、心理记录和 AI 能力放到同一套系统里。

这份文档只回答三个问题：

1. 代码主要分布在哪里
2. 系统从抽象上如何分层
3. 数据、服务和文档之间如何关联

它不是规则手册，也不是实现细节全集。更细的约束、规格和执行信息应分别去 `docs/docs-rules/`、`docs/coding-rules/`、`docs/specs/` 等位置查看。

## Architecture Boundaries

`docs/ARCHITECTURE.md` 负责描述：

- 项目的主要目录和模块职责
- 前端与后端的抽象分层
- 关键数据流和依赖方向
- 文档体系在项目中的位置

`docs/ARCHITECTURE.md` 不负责描述：

- 具体 API 字段和 schema 契约
- 单个功能模块的长期业务规格
- 当前任务的执行步骤
- 局部实现技巧和临时方案

## Physical Structure

项目当前可以先按以下物理结构理解：

| 路径 | 作用 |
| ---- | ---- |
| `frontend/` | React + Electron 前端，负责界面、交互、桌面壳层与前端侧同步逻辑 |
| `lifeprism/` | Python 后端与核心域逻辑，负责配置、服务、数据处理、LLM 能力、存储与监控 |
| `scripts/` | 项目脚本，当前主要包含文档/CI 检查脚本 |
| `test/` | 测试、场景、测试数据与数据库辅助工具 |
| `templates/` | 用户、代理、日记等模板资产 |
| `docs/` | 项目文档资产，包括规则、规格、计划、架构地图和决策记录 |
| `assets/` | 项目级静态资源 |

## Logical Layers

从抽象层看，项目主要分成 6 层：

| 层级 | 说明 |
| ---- | ---- |
| Interface Layer | 前端页面、浮窗、对话框和桌面应用壳层，负责用户入口 |
| Application Layer | 前后端的应用编排逻辑，负责路由、同步、页面装配和服务调度 |
| Domain Layer | 目标、时间追踪、习惯、情绪、日记、摘要上下文等核心业务能力 |
| Intelligence Layer | LLM 分类、聊天、summary context、工具与 provider 抽象 |
| Infrastructure Layer | 配置、数据库、存储 provider、监控进程、日志与资源初始化 |
| Documentation Layer | 规则、规格、计划、架构决策与 CI 报告，用于维护代码与文档一致性 |

这些层不是完全按目录一一对应，但可以作为第一次理解仓库时的主视角。

## Frontend Architecture

前端位于 `frontend/`，当前是一个以 React 为核心、Electron 负责桌面集成的多模块应用。

主结构可以理解为：

- `apps/`：按业务模块拆分的应用区，目前包括 `lifewatch`、`goals`、`habits`、`mindspace`、`settings`、`addons`
- `core/`：跨应用共享的组件、服务、类型、上下文和工具
- `shell/`：主应用壳层与导航，负责把多个业务模块组织到统一桌面界面中
- `dialogs/`：独立对话框窗口
- `floating/`：浮窗入口，当前包含 `what-am-i-doing`
- `electron/`：Electron 主进程、预加载和更新逻辑

入口上，`frontend/App.tsx` 负责做三件事：

1. 根据路由分流主窗口、浮窗和对话框
2. 初始化前端到后端的 API 配置
3. 在主窗口启动后触发增量同步与系统警告加载

因此前端并不只是静态 UI，而是承担了桌面入口、窗口编排和部分同步编排职责。

## Backend Architecture

后端位于 `lifeprism/`，当前以 FastAPI 服务、数据处理链和本地存储为核心。

主要目录职责如下：

| 路径 | 作用 |
| ---- | ---- |
| `lifeprism/server/` | FastAPI 入口、API、schemas、services、providers |
| `lifeprism/processors/` | ActivityWatch 数据清洗、缓存匹配、分类收集与处理主链 |
| `lifeprism/llm/` | 聊天、分类、summary context、provider、工具与 agent loop |
| `lifeprism/config/` | 配置读取、provider 管理、配置迁移 |
| `lifeprism/repository/` | SQLite 初始化、迁移、资源初始化与基础数据访问 |
| `lifeprism/monitor/` | 内置监控进程与窗口监控能力 |
| `lifeprism/utils/` | 日志、异常、通用工具、单例等基础设施 |

`lifeprism/server/` 的主分层仍然是：

- `api/`：HTTP 路由与请求入口
- `services/`：业务编排和领域服务
- `providers/`：面向数据库或具体资源的访问层
- `schemas/`：接口数据结构定义

`lifeprism/server/main.py` 是后端总入口。它先初始化配置，再导入路由和数据库相关模块，最后在应用生命周期中完成资源初始化、数据库初始化、迁移执行、默认数据装载和可选监控进程启动。

## Core Data Flows

当前第一次阅读项目时，优先理解以下 3 条主干流向。

### 1. ActivityWatch 数据处理流

这是 LifeWatch 的核心基础链路：

`ActivityWatch / monitor data`
→ `processor provider`
→ `EventTransformer`
→ `CacheMatcher`
→ `ClassifyCollector`
→ `LLM classify`
→ `CategoryCache / repository`
→ `server services / APIs`
→ `frontend views`

这条链路把原始事件变成可视化、可统计、可总结的个人活动数据。

### 2. 前后端交互流

主窗口启动后，前端先完成 API 地址探测，再通过 `syncService` 调用后端同步接口；后端服务层从存储和处理链取数后返回给前端页面或共享组件。

可简化理解为：

`React UI`
→ `frontend/core/services`
→ `FastAPI api`
→ `services`
→ `providers / repository / llm`
→ `API response`
→ `frontend apps`

### 3. 配置与启动流

项目启动时，配置优先级和初始化顺序非常关键：

`settings_manager`
→ 解析配置路径与数据路径
→ 初始化日志
→ 后端导入其他模块
→ 初始化数据库和资源
→ 启动监控/启动channel/agent loop

这意味着配置层是整个后端启动链的前置依赖。

## Key Dependencies

第一次理解项目时，可以先把后端主依赖方向记成：

`utils -> config -> repository -> monitor -> processors -> server`

同时还要补上一条智能能力链：

`utils / config / repository -> llm -> server`

对应到代码层，可以这样理解：

1. `utils`
   - 最底层通用能力
   - 提供日志、异常、单例和基础工具

2. `config`
   - 建立在 `utils` 之上
   - 负责路径、配置文件、provider 配置和启动前置初始化

3. `repository`
   - 依赖 `config` 和 `utils`
   - 负责数据库连接、基础 provider、初始化和迁移

4. `monitor`
   - 依赖 `repository`、`config` 和 `utils`
   - 负责窗口监控与数据采集入口

5. `processors`
   - 依赖 `repository`、`config`、`utils`
   - 同时调用部分 `llm` 类型与分类能力
   - 负责把原始事件清洗为可分类、可持久化的数据

6. `llm`
   - 依赖 `utils`、`config`、`repository`
   - 提供分类、聊天、summary context、agent loop 和 provider 抽象

7. `server`
   - 位于对外服务层
   - 汇总 `repository`、`processors`、`llm`、`config` 的能力，对前端暴露 API

需要特别注意的是，当前实现里 `llm` 和 `server` 并不是完全严格的单向依赖：

- `server` 明确依赖 `llm`
- `llm` 中的部分 provider / summary context 代码也反向依赖了 `server` 的 provider 或 service

因此，当前更准确的描述是：

- 主体结构上，`server` 是对外汇总层
- 但 `llm` 与 `server` 之间存在现实代码耦合，还不是完全解耦的独立层

对第一次阅读项目的人来说，先把它理解为“以 `utils/config/repository` 为底座，`monitor/processors/llm` 提供能力，`server` 对外汇总，`frontend` 通过 HTTP 使用 `server`”即可。

## Update Triggers

以下变化通常意味着应回看并更新本文件：

1. 顶层目录职责发生变化
2. 前端或后端的主分层发生变化
3. 关键数据流被重构
4. 关键依赖方向或启动顺序发生变化
5. 文档体系的分类和职责边界发生变化
