# 打包环境 SSH 隧道连接失败：win32timezone 缺失

## Bug简述

PyInstaller 打包环境（LifePrism-Setup-0.1.3.exe）SSH 隧道启动失败，错误 `ModuleNotFoundError: No module named 'win32timezone'`；开发环境正常。

## 复用场景

- PyInstaller 打包 + asyncssh 库 + Windows 平台的组合
- 任何"开发环境正常、打包环境异常"的 pywin32 子模块缺失问题
- 第三方库默认初始化未使用功能（GSSAPI）触发运行时导入失败的同类问题

## 代码位置

- `lifeprism/sync/ssh_tunnel.py:179`（`SSHTunnel.connect` 中 `asyncssh.connect` 调用）
- 错误链路：`sync_client.py:331 _start_ssh_tunnel` → `ssh_tunnel.py:179 connect` → `asyncssh.connection.connect` → `asyncssh.gss_win32.GSSClient.__init__:173` → `sspi.ClientAuth:202` → `import win32timezone`

## 发生原因

1. asyncssh 在 Windows 上默认尝试初始化 GSSClient（即使项目用密钥认证）
2. asyncssh `gss.py` 顶层 try/except `ImportError` 只在 `import sspi` 时生效；`sspi` 顶层导入成功（仅 import 模块对象），但 `ClientAuth()` 运行时才触发 `win32timezone` 导入
3. asyncssh `connection.py:3317` 的 try/except 只捕获 `GSSError`，**不捕获 `ModuleNotFoundError`**
4. PyInstaller 打包环境未收集 `win32timezone`（pywin32 子模块），触发 `ModuleNotFoundError` 直接冒泡

## 最佳方案

在 `asyncssh.connect()` 调用中显式传 `options=asyncssh.SSHClientConnectionOptions(gss_host='')`，利用 asyncssh `connection.py:3314` 的 `if gss_host:` 短路判断（空字符串为 falsy）跳过 GSSClient 实例化：

```python
self._connection = await asyncssh.connect(
    host=self.host,
    port=self.port,
    username=self.username,
    client_keys=[key_obj],
    known_hosts=None,
    # 显式禁用 GSSAPI：避免触发 sspi → win32timezone 导入链
    options=asyncssh.SSHClientConnectionOptions(gss_host=''),
)
```

**为何不通过 `lifeprism.spec` hiddenimports 收集 pywin32 子模块**：
- `win32timezone` 可能只是冰山一角，`sspi.ClientAuth()` 内部可能还触发其他 pywin32 子模块导入
- pywin32 升级或 asyncssh 升级可能引入新子模块依赖，维护成本高
- 项目用密钥认证，GSSAPI 是不需要的功能，禁用比打包完整依赖更符合最小依赖原则

## 验证

- 回归测试：`test/core/unit/sync/test_ssh_tunnel.py::test_connect_disables_gssapi` 验证 `asyncssh.connect` 传入 `options.gss_host == ''`
- 打包验证：重新打包后，在打包环境点击"测试连接"，日志 `%LOCALAPPDATA%\LifePrism\lifeprismData\debug_logs\lifeprism.log` 不再出现 `No module named 'win32timezone'`

## 相关文档

- Spec：`docs/specs/2026-07-26-data-sync-ssh-tunnel-spec.md` v1.1 "Windows GSSAPI 禁用"章节
- Flow：`docs/flows/2026-07-26-ssh-tunnel-flow.md` v1.1 反常设计 5
