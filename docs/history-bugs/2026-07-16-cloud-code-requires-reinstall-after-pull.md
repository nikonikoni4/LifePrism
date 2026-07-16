---
version: 1.1
created_at: 2026-07-16
updated_at: 2026-07-16
last_updated: 用户二次同步测试确认根因，git pull 后需重新 pip install -e . 并重启服务才能生效
abstract: 云端服务器 git pull 后 Python 运行时不热更新，需重新 pip install -e . 并重启 uvicorn。已通过二次同步确认。
---

# 云端 git pull 后代码未热更新

## 元信息

- **发生时间**: 2026-07-16
- **修复状态**: ✅ 已确认（运维流程 bug，非代码 bug）
- **影响范围**: 云端所有 Python 模块（sync_cloud_api.py、sync_client.py 等）
- **bug 类型**: 部署/运维问题（pip install -e . 编辑模式 git pull 后不自动热更新）
- **严重程度**: 高

## 触发规则

在以下场景时阅读此文档：
- 排查"git pull 后代码已更新但行为仍为旧版本"的问题
- 同步黑名单（EXCLUDED_FILENAMES）不生效、新增的日志/功能在云端无输出
- 云端采用 `pip install -e .` 的编辑模式部署
- 排查"源码层逻辑正确但运行时行为异常"的问题
- 讨论云端服务器部署流程是否需要增加 `pip install -e .` 步骤

## Bug 简述

云端服务器（`123.56.49.198`）部署方式为 `pip install -e .`（编辑模式），正常情况应随着 git pull 自动热更新代码。
但实际出现过 git pull 后代码文件已是最新（如 commit `bcba5b74` 包含同步黑名单 `EXCLUDED_FILENAMES`），
但 uvicorn 运行时仍加载旧版本模块的行为，导致同步黑名单完全不生效。

推测根因：`pip install -e .` 虽创建了 `.pth` 链接到源码目录，但某些场景下 Python 模块加载
仍使用已缓存的 `.pyc` 或 egg-link 指向的旧路径，需要重新 `pip install -e .` 才能绑定到最新代码。

## 现象

1. git pull 后 `lifeprism/sync/constants.py` 文件中 `EXCLUDED_FILENAMES = {"chat_history.json", "bootstrap.md"}` 已存在
2. 但云端 `/pull-files/check` 端点仍返回黑名单文件，`all_paths` 包含 `bootstrap.md`
3. 新增的诊断日志（如 "黑名单过滤生效，跳过 X 个文件"）在云端日志中无输出
4. 客户端日志显示黑名单生效，但云端同步行为仍为旧版本逻辑

## 代码位置

**受影响模块**：云端所有通过 `pip install -e .` 安装的 Python 模块，尤其是：

- [lifeprism/sync/constants.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/constants.py#L12) — `EXCLUDED_FILENAMES` 定义
- [lifeprism/server/api/sync_cloud_api.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/api/sync_cloud_api.py#L531) — `/pull-files/check` 端点
- [lifeprism/server/api/sync_cloud_api.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/api/sync_cloud_api.py#L814) — `/push-files` 端点
- [lifeprism/sync/sync_client.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py) — SyncClient 全部逻辑

## 发生原因

经二次同步测试确认：`pip install -e .` 在 git pull 后不会自动让 uvicorn 加载新代码。

1. `pip install -e .` 的编辑模式通过 `.egg-link` 或 `.pth` 文件将项目目录加入 `sys.path`
2. uvicorn 在生产模式（非 `--reload`）下启动后不会监控文件变更，已加载的模块缓存在内存中
3. git pull 更新 `.py` 文件后，uvicorn 进程仍使用启动时加载的模块版本
4. 即使删除 `.pyc` 缓存，uvicorn 也不会重新加载模块——因为生产模式不做文件监控
5. **必须重启 uvicorn 进程**才能加载新代码；如果采用 `pip install .`（非编辑模式），还需要重新安装包

### 确认过程

1. 第一次 git pull 后直接重启服务 → 云端行为仍为旧版本（黑名单不生效）
2. 停止服务 → `pip install -e .` → 重启服务 → 云端行为变为新版本（黑名单生效）

## 标准部署流程

每次更新云端代码时必须按以下顺序执行：

```bash
cd /path/to/lifeprism
git pull
pip install -e .          # 重新链接到最新源码
systemctl restart lifeprism-web   # 或 kill + 重启 uvicorn
```

> ⚠️ 仅 git pull + 重启不足以加载新代码，必须重新 `pip install -e .`。

## 长期建议

1. **部署脚本规范化**：在 `scripts/deployment/` 下创建 `deploy.sh`，包含 `git pull` → `pip install -e .` → 重启服务三步
2. **版本自检**：启动时在日志中打印当前 git commit hash，方便对比预期版本和实际运行版本
3. **考虑切换到 pip install .（非编辑模式）**：彻底消除路径指向歧义，代价是每次更新需重新安装

## 验证方法

1. git pull 后，检查云端日志是否出现新增的诊断信息
2. 对比 git log 中的 commit hash 和运行时行为
3. 在云端服务器执行以下命令确认实际加载的模块路径：

```bash
python -c "import lifeprism.sync.constants; print(lifeprism.sync.constants.__file__)"
# 输出路径应与 git 仓库路径一致，而非 site-packages 下的旧副本
```
