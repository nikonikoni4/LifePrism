---
issue: 01
title: 8102 端口默认绑定 127.0.0.1（环境变量可覆盖）
triage: ready-for-agent
slice: 1
---

# 8102 端口默认绑定 127.0.0.1（环境变量可覆盖）

## Parent

PRD: [.scratch/ssh-tunnel-integration/prd.md](../prd.md)

## What to build

云端服务器 8102 端口默认绑定地址从硬编码 `0.0.0.0` 改为 `127.0.0.1`，关闭公网暴露。同时支持通过环境变量 `LIFEPRISM_API_HOST` 覆盖默认绑定地址，便于在测试场景或需要保留公网访问的特殊场景下灵活配置。

修改后服务器启动时：
- 默认情况下，8102 端口仅在服务器本机可见（`127.0.0.1`），公网 `nmap` 扫描无法发现
- 设置 `LIFEPRISM_API_HOST=0.0.0.0` 时，恢复原有公网监听行为（仅用于测试或 Nginx 反代场景）
- 启动日志需打印实际绑定地址，便于运维确认

本切片是 SSH 隧道方案的服务器端基础——只有 8102 不暴露公网，SSH 隧道的安全收益才能成立。

## Acceptance criteria

- [ ] 修改 `lifeprism/server/main_agent_only.py` 中 uvicorn.Config 的 host 参数为 `os.environ.get("LIFEPRISM_API_HOST", "127.0.0.1")`
- [ ] 默认启动时 8102 端口绑定 `127.0.0.1`，本机 `curl http://127.0.0.1:8102/api/sync/health` 返回 ok
- [ ] 默认启动时公网访问 8102 端口超时/拒绝（如本地测试可用 `curl http://<本机IP>:8102 --bind 0.0.0.0 --max-time 3` 验证不可达）
- [ ] 设置环境变量 `LIFEPRISM_API_HOST=0.0.0.0` 启动时，8102 端口绑定 `0.0.0.0`（公网可访问，用于测试场景）
- [ ] 启动日志 INFO 级别打印实际绑定地址（如 "uvicorn 启动于 http://127.0.0.1:8102"）
- [ ] 扩展 `test/core/integration/test_agent_only_mode.py` 新增两个测试：
  - 默认配置下 host 为 127.0.0.1
  - 环境变量 LIFEPRISM_API_HOST=0.0.0.0 时 host 覆盖为 0.0.0.0
- [ ] 所有现有测试通过（无回归）
- [ ] 遵循 [coding-rules/backend-core-rules.md](../../../docs/coding-rules/backend-core-rules.md) 的类型注解和日志规范

## Blocked by

None - can start immediately
