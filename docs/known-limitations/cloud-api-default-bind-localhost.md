---
version: 1.0
created_at: 2026-07-27
updated_at: 2026-07-27
last_updated: 创建文档，记录云端 8102 端口默认绑定 127.0.0.1 导致无法通过公网 http 直接访问的已知限制
abstract: 记录 LifePrism 云端 agent-only 模式下 API 端口默认绑定 127.0.0.1（仅本机访问）的已知限制。这是 SSH 隧道方案的服务端基础设计，关闭公网暴露以保障安全，但导致无法通过公网 IP 直接 http 访问 8102 端口，需通过环境变量 LIFEPRISM_API_HOST=0.0.0.0 覆盖。
---

# 云端 API 端口默认绑定 127.0.0.1 限制

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿，记录云端 8102 端口默认绑定 127.0.0.1 的已知限制 |

---

## 概述

LifePrism 云端 agent-only 模式（`lifeprism/server/main_agent_only.py`）启动时，uvicorn 默认将 API 服务绑定到 `127.0.0.1`，即仅本机可访问，公网无法直接通过 `http://<云端IP>:8102` 访问同步 API。

这是 SSH 隧道方案的服务端基础设计——只有 8102 端口不暴露公网，SSH 隧道（将本地端口转发到云端 `127.0.0.1:8102`）的安全收益才能成立。该行为通过环境变量 `LIFEPRISM_API_HOST` 可覆盖，但默认值有意设为 `127.0.0.1`。

用户若需要直接通过公网 http 访问 8102 端口（如不走 SSH 隧道、Nginx 反代、调试场景），必须显式设置环境变量 `LIFEPRISM_API_HOST=0.0.0.0`，否则连接会被拒绝（连接超时或拒绝）。

---

## 问题描述

`lifeprism/server/main_agent_only.py` 中 [`_get_api_host()`](../../lifeprism/server/main_agent_only.py#L136) 函数默认返回 `127.0.0.1`：

```python
def _get_api_host() -> str:
    """
    读取 API 绑定地址。

    默认 127.0.0.1（仅本机访问，关闭公网暴露，配合 SSH 隧道方案使用）。
    可通过环境变量 LIFEPRISM_API_HOST 覆盖（如 0.0.0.0 用于测试场景或 Nginx 反代）。
    """
    return os.environ.get("LIFEPRISM_API_HOST", "127.0.0.1")
```

代码注释明确说明这是有意设计："默认 127.0.0.1（仅本机访问，关闭公网暴露，配合 SSH 隧道方案使用）"。

`start.sh` 启动 agent-only 模式时不设置 `LIFEPRISM_API_HOST` 环境变量，因此端口不对外暴露。云端架构如下：

```
云端服务器 (123.56.49.198)
┌──────────────────────────────┐
│ Port 8102 只绑定 127.0.0.1  │  ← 公网无法访问
│ 只能从本机 localhost 访问    │
└──────────┬───────────────────┘
           │
           │ SSH 隧道
           │
┌──────────┴───────────────────┐
│ Port 22 (SSHD) 绑定 0.0.0.0  │  ← 公网可以访问
└──────────────────────────────┘

本地客户端通过 SSH 隧道连接到云端 127.0.0.1:8102
而不是直接访问 123.56.49.198:8102
```

---

## 影响范围 + 严重程度

- **影响范围**：云端 agent-only 模式下所有尝试通过公网 http 直接访问 8102 端口的场景
- **严重程度**：低（设计选择，非缺陷；SSH 隧道模式下功能不受影响）

---

## 当前假设

- 系统假设"云端 agent-only 模式仅通过 SSH 隧道被本地客户端访问"
- 系统假设"用户不需要通过公网 IP 直接 http 访问 8102 端口"
- 这是 SSH 隧道方案的服务端基础——只有 8102 不暴露公网，SSH 隧道的安全收益才能成立（详见 issue `01-8102-bind-localhost.md`）

---

## 触发条件

以下场景会触发此限制：

- 用户尝试通过 `http://123.56.49.198:8102` 直接访问云端 API（不走 SSH 隧道）
- 用户部署 Nginx 反向代理时，未设置 `LIFEPRISM_API_HOST=0.0.0.0` 导致 Nginx 无法转发请求到 8102
- 用户在调试或测试场景下希望从外部网络直接 curl 云端 8102 端口

---

## 临时方案或计划改进

- **当前方案**：如需通过公网 http 直接访问 8102 端口，在云端启动 agent-only 前设置环境变量：

  ```bash
  export LIFEPRISM_API_HOST=0.0.0.0
  ./start.sh
  ```

  或修改 `start.sh` 显式注入该环境变量（不推荐，会破坏默认安全配置）。

- **未来增强**：后续可能需要修改默认配置策略，使其在以下场景下更灵活：
  - Nginx 反代模式：自动检测 Nginx 配置或提供独立的 `run_mode` 选项
  - HTTPS 直连模式：配合 `LIFEPRISM_SSL_KEYFILE` / `LIFEPRISM_SSL_CERTFILE` 提供完整的公网 HTTPS 访问能力
  - 当前这些方案尚未确定，仅作为已知限制记录

---

## 相关文档

- 代码实现：[`../../lifeprism/server/main_agent_only.py`](../../lifeprism/server/main_agent_only.py#L136)
- 集成测试：[`../../test/core/integration/test_agent_only_mode.py`](../../test/core/integration/test_agent_only_mode.py#L207)（`test_default_host_is_localhost`、`test_env_var_overrides_host`）
- SSH 隧道方案 Issue：[`../../.scratch/ssh-tunnel-integration/issues/01-8102-bind-localhost.md`](../../.scratch/ssh-tunnel-integration/issues/01-8102-bind-localhost.md)
- SSH 隧道集成 PRD：[`../../.scratch/ssh-tunnel-integration/prd.md`](../../.scratch/ssh-tunnel-integration/prd.md)（User Story 28、29、30）
- SSH 隧道已知限制：[`./ssh-tunnel-limitations.md`](./ssh-tunnel-limitations.md)
- 部署文档：[`../deployment/cloud-https-setup.md`](../deployment/cloud-https-setup.md) "模式 C 配置"
