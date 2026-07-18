# 云端同步端到端测试实战示例（2026-07-18）

## 文档说明

本文档记录 2026-07-18 ~ 2026-07-19 期间对 LifePrism 云端同步进行端到端测试的完整实战过程，作为后续类似测试的参考示例。

**与 `sync-e2e-testing.md` 的关系**：
- `sync-e2e-testing.md`：方法论文档（理论、环境配置、两种测试方式）
- 本文：实战案例（基于真实 bug 修复 + 端到端测试的完整流程）

## 测试目标

测试最近两天提交的两个核心功能：
1. **首次同步全覆盖方案**（基于 `docs/adr/2026-07-17-cloud-init-first-sync-full-clear.md`）
2. **新文件冲突处理方案**（基于 `.scratch/file-conflict-resolution-redesign/`，含 diff3 + LLM 串行合并 + 双备份）

## 测试环境

- **本地仓库**：`D:\desktop\软件开发\LifeWatch-AI`（端口 8101）
- **模拟云端**：`D:\desktop\软件开发\LifeWatch-AI\explore\LifePrism`（端口 8102，agent_only 模式）
- **云端配置**：`explore\LifePrism\localData\cloud_init.yaml`（已配置）
- **Python 环境**：`D:\program\anaconda\envs\lifeprism_dev\python.exe`
- **测试时间**：2026-07-18 ~ 2026-07-19

## 测试流程

### 阶段 A：准备测试环境

#### A.1 重置云端初始化状态

删除云端 `cloud_initialized` 标志文件，使下次本地 sync_once 检测到"未初始化"，重新触发首次同步：

```powershell
Remove-Item -Path "D:\desktop\软件开发\LifeWatch-AI\explore\LifePrism\localData\config\cloud_initialized" -Force -ErrorAction SilentlyContinue
```

#### A.2 准备云端测试数据（验证"全清覆盖"原则）

在云端预先创建以下测试数据（用于验证"云端同步之前的所有数据都是无效数据"原则）：

| 文件 | 类型 | 说明 |
| ---- | ---- | ---- |
| `diary/conflict_test/conflict_demo.md` | templates 外数据 | 预期被清空 |
| `agent/chat/bootstrap.md` | 黑名单内非空文件 | 预期被清空 |
| `user/daily_data/chat_history.json` | 黑名单内非空文件 | 预期被清空 |
| `diary/e2e_empty.md` | 空文件 | 预期被过滤不推送 |
| `diary/e2e_normal.md` | 正常文件 | 预期被推送 |
| `diary/e2e_template_copy.md` | template 副本 | 预期被过滤不推送（hash 严格匹配） |

#### A.3 启动云端服务

```powershell
cd "D:\desktop\软件开发\LifeWatch-AI\explore\LifePrism"
$env:LIFEPRISM_DATA_PATH="D:\desktop\软件开发\LifeWatch-AI\explore\LifePrism\localData"
D:\program\anaconda\envs\lifeprism_dev\python.exe -m lifeprism.server.main_agent_only start
```

验证云端启动：等待 `Agent Loop + WeChat Channel 启动完成` 日志。

#### A.4 启动本地 main 触发同步

```powershell
cd "D:\desktop\软件开发\LifeWatch-AI"
D:\program\anaconda\envs\lifeprism_dev\python.exe -m lifeprism.server.main
```

启动后本地 main 会自动执行 sync_once，检测到云端未初始化 → 触发首次同步全清覆盖。

### 阶段 B：T1 首次同步全覆盖验证

#### B.1 验证清空效果

查看 `localData/debug_logs/sync.log`：

```
INFO sync_client.py func:_full_sync_to_cloud line 335 : 步骤 1/4: 清空云端数据...
INFO sync_client.py func:_full_sync_to_cloud line 342 : 云端清空完成: {'status': 'ok', 'cleared_tables': [...31张...], 'cleared_files': 117, ...}
INFO sync_client.py func:_initial_push_files line 494 : 文件全量推送完成: 117 个文件
INFO sync_client.py func:_advance_local_parent_after_initial_sync line 548 : 首次同步后推进 parent_hash: 117/117 个文件
INFO sync_client.py func:_advance_remote_parent_after_initial_sync line 627 : 首次同步后推进云端 parent_hash: 117/117 个文件
INFO sync_client.py func:_full_sync_to_cloud line 373 : 云端已标记为已初始化
```

#### B.2 验证两端 DB 状态对称

编写调试脚本 `docs/temp/debug_cloud_sync_state.py` 查询两端 `file_sync_state` 表：

```python
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLOUD_DB = ROOT / "explore" / "LifePrism" / "localData" / "dataset" / "lifewatch_ai.db"
LOCAL_DB = ROOT / "localData" / "dataset" / "lifewatch_ai.db"

def query(db_path, file_path):
    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT parent_hash, current_hash FROM file_sync_state WHERE file_path=?",
        (file_path,)
    ).fetchone()
    conn.close()
    return row

for f in ["diary/e2e_normal.md", "diary/e2e_template_copy.md"]:
    print(f"=== {f} ===")
    print("云端:", query(CLOUD_DB, f))
    print("本地:", query(LOCAL_DB, f))
```

期望输出：两端 `parent_hash` 和 `current_hash` 完全一致。

### 阶段 C：T4/T5/T6 冲突解决测试

#### C.1 准备 base content（关键！）

`_fetch_remote_base_content` 从 `localData/backups/docs/{timestamp}/` 查找匹配 `parent_hash` 的历史版本作为 diff3 的 base。**若文件创建后未经过备份周期（每天 03:00 执行），需要手动创建备份**：

```powershell
New-Item -Path "D:\desktop\软件开发\LifeWatch-AI\localData\backups\docs\2026-07-18T16-30-00\diary" -ItemType Directory -Force | Out-Null
Copy-Item "D:\desktop\软件开发\LifeWatch-AI\localData\diary\e2e_normal.md" "D:\desktop\软件开发\LifeWatch-AI\localData\backups\docs\2026-07-18T16-30-00\diary\e2e_normal.md" -Force
Copy-Item "D:\desktop\软件开发\LifeWatch-AI\localData\diary\e2e_template_copy.md" "D:\desktop\软件开发\LifeWatch-AI\localData\backups\docs\2026-07-18T16-30-00\diary\e2e_template_copy.md" -Force
```

#### C.2 制造冲突场景

**T4 测试（diff3 自动合并）** - 双方在不同位置修改：
- 本地 `e2e_normal.md`：第 7 行新增"这是本地修改（第二轮）：用于触发 diff3 自动合并"
- 云端 `e2e_normal.md`：第 12 行新增"云端修改（第二轮）：用于触发 diff3 自动合并"

**T5 测试（LLM 串行合并）** - 双方在同一位置修改：
- 本地 `e2e_template_copy.md`：第 11 行改为"本地修改（第二轮）：T5 LLM 串行合并测试 - 本地版本"
- 云端 `e2e_template_copy.md`：第 11 行改为"云端修改（第二轮）：T5 LLM 串行合并测试 - 云端版本"

#### C.3 触发同步并验证

停止本地 main（Ctrl+C 或 StopCommand），重新启动：

```powershell
cd "D:\desktop\软件开发\LifeWatch-AI"
D:\program\anaconda\envs\lifeprism_dev\python.exe -m lifeprism.server.main
```

查看 `sync.log`：

```
INFO sync_client.py func:_sync_files_full_flow line 2112 : _sync_files_full_flow: 矩阵判定完成 PULL=0, PUSH=0, CONFLICT=2, SKIP=115
INFO sync_client.py func:_sync_files_full_flow line 2145 : _sync_files_full_flow: 非 JSONL 冲突走 AI 合并: 2 个: ['diary/e2e_normal.md', 'diary/e2e_template_copy.md']
INFO conflict_backup.py func:backup_conflict_versions line 216 : backup_conflict_versions: 已备份冲突文件 local+remote 版本 file_path=diary/e2e_normal.md
INFO conflict_resolution.py func:resolve_conflict_blocks line 681 : resolve_conflict_blocks: 串行处理完成，成功=1, 失败=0, 总计=1
INFO sync_client.py func:_resolve_conflicts line 1945 : _resolve_conflicts: LLM 串行处理完成 diary/e2e_template_copy.md，成功=1, 失败=0, 总计=1
INFO sync_client.py func:_resolve_conflicts line 2000 : _resolve_conflicts: 冲突解决完成，成功 2/2
```

#### C.4 验证最终文件内容

- 本地 `e2e_normal.md` 和云端 `e2e_normal.md` 应包含本地+云端的双处修改（diff3 自动合并）
- 本地 `e2e_template_copy.md` 和云端 `e2e_template_copy.md` 应包含 LLM 合并结果（两端内容一致）

#### C.5 验证 sync_conflict/ 双备份

```powershell
Get-ChildItem -Path "D:\desktop\软件开发\LifeWatch-AI\localData\sync_conflict" -Recurse -Force | Format-Table FullName, Length -AutoSize
```

期望输出：每次冲突都生成 `*.local.md` 和 `*.remote.md` 双备份。

### 阶段 D：T2 二次启动增量同步验证

再次启动本地 main，查看 `sync.log`：

期望：**未出现** "云端未初始化，执行首次同步（全清覆盖）..." 日志，直接走增量同步流程（pull_from_remote → push_to_remote → _sync_files_full_flow）。

## 关键调试技巧

### D.1 查看实时日志

```powershell
# 本地 sync.log（专用日志，500KB 滚动）
Get-Content "D:\desktop\软件开发\LifeWatch-AI\localData\debug_logs\sync.log" -Tail 60 -Encoding UTF8

# 本地 lifeprism.log（全局日志）
Get-Content "D:\desktop\软件开发\LifeWatch-AI\localData\debug_logs\lifeprism.log" -Tail 60 -Encoding UTF8

# 云端 lifeprism.log
Get-Content "D:\desktop\软件开发\LifeWatch-AI\explore\LifePrism\localData\debug_logs\lifeprism.log" -Tail 60 -Encoding UTF8
```

### D.2 停止所有 Python 进程

```powershell
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
```

### D.3 查询两端 DB 状态

参考阶段 B.2 的 `debug_cloud_sync_state.py` 脚本。

### D.4 计算文件 hash 验证

```python
# docs/temp/debug_cloud_file_hash.py
from pathlib import Path
from lifeprism.sync.hash_utils import compute_file_hash

CLOUD = Path(r"D:\desktop\软件开发\LifeWatch-AI\explore\LifePrism\localData")
LOCAL = Path(r"D:\desktop\软件开发\LifeWatch-AI\localData")

for rel in ["diary/e2e_normal.md", "diary/e2e_template_copy.md"]:
    c_hash = compute_file_hash((CLOUD / rel).read_bytes())
    l_hash = compute_file_hash((LOCAL / rel).read_bytes())
    print(f"{rel}: cloud={c_hash[:16]}, local={l_hash[:16]}, equal={c_hash == l_hash}")
```

## 测试覆盖项

| 测试项 | 内容 | 关键验证点 |
| ------ | ---- | ---------- |
| T1 | 首次同步全覆盖 | 云端旧数据清空、117 文件覆盖、两端 parent_hash 对称、cloud_initialized 生成 |
| T2 | 二次启动增量同步 | sync_once 未进入首次同步分支 |
| T3 | 空文件+template 过滤 | 空文件过滤 51 个、template 过滤 10 个 |
| T4 | diff3 自动合并 | CONFLICT=2、双方不同位置修改被保留、无冲突标记 |
| T5 | LLM 串行合并 | 1 个冲突块、LLM 合并成功 1/1、两端内容一致 |
| T6 | sync_conflict/ 双备份 | 每次冲突生成 local.md + remote.md |

## 实战中遇到的 Bug

### Bug 2026-07-18-cloud-parent-hash-not-advanced-after-first-sync

**现象**：T4/T5/T6 冲突未触发，矩阵判定 `PUSH=2, CONFLICT=0` 而非预期的 `CONFLICT=2`。

**根因**：`_full_sync_to_cloud` 步骤 3 后只调用 `_advance_local_parent_after_initial_sync` 推进本地 parent_hash，**未调用任何云端端点推进云端 parent_hash**。导致首次同步后两端状态不对称（本地 parent_hash=H0, 云端 parent_hash=None），下次同步矩阵走 Row 5 (PUSH) 而非 Row 9 (CONFLICT)。

**修复**：新增 [`_advance_remote_parent_after_initial_sync`](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L556-L638) 方法，分批调用 `/pull-files/commit` 推进云端 parent_hash。

**详细记录**：[`docs/history-bugs/2026-07-18-cloud-parent-hash-not-advanced-after-first-sync.md`](file:///d:/desktop/软件开发/LifeWatch-AI/docs/history-bugs/2026-07-18-cloud-parent-hash-not-advanced-after-first-sync.md)

## 完整测试报告

详见：[`docs/generated/018/2026-07-18-sync-e2e-test-report.md`](file:///d:/desktop/软件开发/LifeWatch-AI/docs/generated/018/2026-07-18-sync-e2e-test-report.md)

## 后续类似测试建议

1. **先重置云端状态**：删除 `cloud_initialized` 标志文件，确保从首次同步开始测试
2. **准备 base content**：冲突测试前，手动创建 `backups/docs/{timestamp}/` 备份目录，否则 diff3/LLM 合并会降级为 LWW
3. **分阶段测试**：T1 → T2 → T3 → T4/T5/T6，每阶段都验证 DB 状态对称
4. **编写调试脚本**：查询两端 DB 状态、计算文件 hash，用于快速定位问题
5. **分析 sync.log**：关键日志点包括矩阵判定、冲突解决、parent_hash 推进、mark-initialized
