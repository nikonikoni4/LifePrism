使用 tdd skill 完成任务

# Issue #16: 历史数据时区迁移脚本编写和执行

## Parent

`.scratch/utc-timezone-migration/prd.md`

## What to build

编写并执行数据库历史数据的时区迁移脚本，将本地时区数据转为 UTC。

**迁移策略**：
- 假设所有历史数据为 UTC+8（北京时间），统一减 8 小时转为 UTC
- 排除 3 张已经是 UTC 的旧表（需在排查时确认具体是哪 3 张表）

**迁移脚本**：
- 创建 `lifeprism/repository/migrations/scripts/m008_migrate_to_utc.py`
- 读取 `docs/generated/backend-time-fields-inventory.md` 获取所有时间字段清单
- 对每个表的每个时间字段执行：`UPDATE table_name SET time_field = datetime(time_field, '-8 hours') WHERE time_field IS NOT NULL;`
- 记录迁移日志（表名、字段名、影响行数）
- 抽样验证迁移结果

**数据库测试环境**：
- 备份数据库：`D:\desktop\软件开发\LifeWatch-AI\localData\dataset\lifewatch_ai - utc-refactor.db`（只读，作为备份）
- 测试数据库：`D:\desktop\软件开发\LifeWatch-AI\localData\dataset\lifewatch_ai.db`（用于迁移测试）
- 每次测试完成后，从备份数据库重置测试数据库

**执行流程（两阶段）**：

**阶段 1：单元测试（先确保代码正确性）**
1. 编写迁移脚本 `m008_migrate_to_utc.py`
2. 编写单元测试验证迁移逻辑：
   - 测试时间减 8 小时的计算正确性
   - 测试排除 UTC 旧表的逻辑
   - 测试迁移日志记录功能
3. 运行单元测试，确保通过

**阶段 2：数据迁移测试**
1. 从备份数据库恢复测试数据库
2. 在测试数据库执行迁移脚本
3. 验证迁移结果：
   - 抽样检查时间字段是否正确减 8 小时
   - 检查 UTC 旧表是否未被修改
   - 验证迁移日志完整性
4. 验证关键功能（数据同步、定时任务、前端时间显示）
5. 如果测试失败，从备份数据库重置后重新测试
6. 测试通过后，备份生产数据库并执行迁移
7. 监控错误日志

**⚠️ 重要**：此 issue 完成后，需要由 Issue #19 审核迁移结果，确认数据正确后才能进入生产环境迁移。

## Acceptance criteria

**阶段 1：单元测试**
- [ ] 迁移脚本已编写完成
- [ ] 已编写单元测试验证迁移逻辑
- [ ] 单元测试全部通过

**阶段 2：数据迁移测试**
- [ ] 已从备份数据库恢复测试数据库
- [ ] 已在测试数据库执行迁移脚本
- [ ] 已抽样验证时间字段迁移正确（减 8 小时）
- [ ] 已验证 UTC 旧表未被修改
- [ ] 已验证迁移日志完整性
- [ ] 已验证数据同步功能正常
- [ ] 已验证定时任务触发时间正确
- [ ] 已验证前端时间显示正确
- [ ] 测试通过后，已备份生产数据库
- [ ] 已在生产环境执行迁移脚本
- [ ] 已监控错误日志，无异常

## Blocked by

- Issue #2 - Repository 层基础迁移
- Issue #3 - Repository 层各 Provider 迁移
- Issue #4 - 数据同步服务迁移
- Issue #5 - 定时任务服务迁移
- Issue #6 - 报表和统计服务迁移
- Issue #7 - 目标/习惯/日记服务迁移
- Issue #8 - 其他服务迁移
- Issue #9 - API 层迁移
- Issue #10 - LLM 模块迁移
- Issue #11 - Monitor 模块迁移
（所有后端代码修改必须完成）
