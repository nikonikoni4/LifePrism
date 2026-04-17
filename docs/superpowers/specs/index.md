---
version: 1.1
created_at: 2026-04-10
updated_at: 2026-04-17
last_updated: 新增日记 AI 总结设计稿索引
abstract: superpowers 设计文档索引，记录技能相关设计稿和实现前设计稿的主题与用途。
---

# Superpowers Specs Index

## Overview

本索引用于导航 `docs/superpowers/specs/` 下的设计稿。

## 使用规则

1. 每新增一个正式设计稿，都在此索引补一条摘要。
2. 摘要只说明文档主题和用途，不复制正文。
3. 设计稿用于实现前收敛方案，不直接等同于正式 spec。

## 文档列表

| 文件 | 简要说明 |
| ---- | -------- |
| [2026-04-10-ci-check-skill-design.md](2026-04-10-ci-check-skill-design.md) | CI-check skill 设计稿，定义检查流程、子 agent 分派、配置状态与报告契约。 |
| [2026-04-17-diary-ai-summary-design.md](2026-04-17-diary-ai-summary-design.md) | 日记 AI 总结设计稿，定义只读总结卡片、手动触发 API、LLM 调用、数据库覆盖写入和测试边界。 |
