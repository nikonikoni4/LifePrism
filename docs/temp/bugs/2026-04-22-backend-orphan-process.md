# 2026-04-22 打包环境下退出后后端进程依然运行

## Bug 信息

- **发现日期**: 2026-04-22
- **严重程度**: 中等（影响用户体验，占用系统资源）
- **影响范围**: Windows 打包环境下的进程清理
- **状态**: 待修复
- **相关文件**: 
  - `frontend/electron/main.cjs` (第695-699行)
  - `lifeprism/server/main.py` (第217-226行)
  - `lifeprism/monitor/windows_monitor/main.py`

## 问题描述

在 Windows 打包环境下，当用户从托盘菜单选择"退出 LifePrism"时，Electron主进程退出，但是：

1. 后端进程（lifeprism-backend.exe）被杀死
2. **监控子进程（LifePrism-Monitor）依然在后台运行**
3. 监控进程变成孤儿进程，继续占用系统资源
4. 用户需要手动从任务管理器杀死监控进程

## 症状表现

### 任务管理器表现

退出 LifePrism 后：
- ✅ `lifeprism.exe` (Electron主进程) 已退出
- ✅ `lifeprism-backend.exe` (后端进程) 已退出
- ❌ Python 监控进程依然在运行（进程名可能是 `python.exe` 或内嵌在后端exe中）

### 日志表现

Electron日志（`localData/debug_logs/electron.log`）：
```
[Electron] 应用即将退出...
[Electron] 正在关闭后端进程...
[Backend] 进程退出，代码: 1
```

**缺失的日志**（后端清理逻辑未执行）：
```
正在终止监控进程 (PID: xxxxx)...
监控进程已清理
```

## 根本原因分析

### 1. 进程层级关系

```
Electron主进程 (lifeprism.exe)
  └─ 后端进程 (lifeprism-backend.exe)
       └─ 监控子进程 (LifePrism-Monitor) ← 孤儿进程
```

### 2. 核心问题：`backendProcess.kill()` 只杀死直接子进程

**问题代码**（`frontend/electron/main.cjs:695-699`）：

```javascript
// 关闭后端进程
if (backendProcess) {
    console.log('[Electron] 正在关闭后端进程...');
    backendProcess.kill();  // ← 问题在这里
}
```

**问题分析**：

1. `backendProcess.kill()` 在 Windows 上默认发送 `SIGTERM` 信号
2. 信号只发送给**直接子进程**（lifeprism-backend.exe）
3. **不会传递给孙进程**（监控子进程）
4. 后端进程被强制杀死，FastAPI 的 `lifespan` 清理逻辑**无法执行**
5. 监控子进程变成**孤儿进程**，被系统接管，继续运行

### 3. Windows 进程管理的特殊性

在 Windows 上：
- `spawn()` 创建的子进程默认不是进程组
- 父进程被杀死时，Windows **不会自动终止子进程**
- 子进程会被系统的 init 进程（或 CSRSS）接管

### 4. 后端清理逻辑无法执行

后端有正确的清理代码（`lifeprism/server/main.py:217-226`）：

```python
# 关闭时：清理监控进程
if hasattr(app.state, "monitor_process") and app.state.monitor_process:
    proc = app.state.monitor_process
    if proc.is_alive():
        logger.info(f"正在终止监控进程 (PID: {proc.pid})...")
        proc.terminate()
        proc.join(timeout=5)
        if proc.is_alive():
            logger.warning("监控进程未能在 5 秒内退出，正在强制杀死...")
            proc.kill()
        logger.info("监控进程已清理")
```

**但是**：
- 这段代码在 FastAPI 的 `lifespan` 上下文管理器的 `yield` 之后
- 只有当 uvicorn **正常关闭**时才会执行
- 当 Electron 使用 `backendProcess.kill()` 强制杀死后端时，这段清理代码**根本不会执行**

### 5. 为什么开发环境没有这个问题

开发环境通常通过以下方式停止：
- Ctrl+C：发送 `SIGINT` 信号
- IDE 停止按钮：发送 `SIGTERM` 信号并等待

这些方式都会：
1. 让 uvicorn 捕获信号
2. 触发 FastAPI 的 `lifespan` 清理逻辑
3. 正确终止监控进程

## 修复方案对比

### 方案1：Electron端 - 使用进程树杀死（推荐 ⭐⭐⭐⭐⭐）

**原理**：在 Windows 上使用 `taskkill /T` 命令杀死整个进程树，包括所有子进程和孙进程。

**修改位置**：`frontend/electron/main.cjs:695-699`

**优点**：
- ✅ 改动最小（只需修改 Electron 端）
- ✅ 彻底解决问题（杀死整个进程树）
- ✅ 不依赖后端的清理逻辑
- ✅ 适用于所有子进程场景
- ✅ 立即生效，无需等待

**缺点**：
- ⚠️ 强制杀死，后端无法执行清理逻辑（但当前也是这样）
- ⚠️ Windows 特定方案（需要平台判断）

**实现代码**：
```javascript
// 关闭后端进程
if (backendProcess) {
    console.log('[Electron] 正在关闭后端进程...');
    
    if (process.platform === 'win32') {
        // Windows: 使用 taskkill 杀死进程树
        const { exec } = require('child_process');
        exec(`taskkill /pid ${backendProcess.pid} /T /F`, (error) => {
            if (error) {
                console.error('[Electron] 杀死后端进程树失败:', error);
            } else {
                console.log('[Electron] 后端进程树已终止');
            }
        });
    } else {
        // Unix/Linux/macOS: 使用 SIGTERM
        backendProcess.kill();
    }
}
```

---

### 方案2：Electron端 - 优雅关闭后端（最佳实践 ⭐⭐⭐⭐⭐）

**原理**：先通过 HTTP 请求让后端优雅关闭（执行清理逻辑），如果超时则强制杀死。

**修改位置**：
- `lifeprism/server/main.py`（添加关闭API）
- `frontend/electron/main.cjs:695-699`（调用关闭API）

**优点**：
- ✅ 后端能执行清理逻辑（正确终止监控进程）
- ✅ 符合最佳实践（优雅关闭）
- ✅ 跨平台方案
- ✅ 数据安全（数据库连接正常关闭）
- ✅ 日志完整（记录完整的关闭流程）

**缺点**：
- ❌ 需要后端添加关闭 API 端点
- ❌ 实现稍复杂（需要超时处理）
- ⚠️ 依赖网络通信（如果后端已经挂了则无法优雅关闭）

**实现代码**：

**步骤1**：后端添加关闭端点（`lifeprism/server/main.py`）
```python
@app.post("/api/v2/system/shutdown", tags=["System"])
async def shutdown():
    """优雅关闭服务器"""
    logger.info("收到关闭请求，正在优雅关闭...")
    
    # 延迟关闭，让响应先返回
    import asyncio
    asyncio.create_task(_delayed_shutdown())
    
    return {"status": "shutting_down"}

async def _delayed_shutdown():
    await asyncio.sleep(0.5)  # 等待响应返回
    import os
    os._exit(0)  # 触发 lifespan 清理逻辑
```

**步骤2**：Electron 调用关闭 API
```javascript
// 关闭后端进程
if (backendProcess) {
    console.log('[Electron] 正在优雅关闭后端...');
    
    // 尝试优雅关闭
    const axios = require('axios');
    const shutdownTimeout = setTimeout(() => {
        console.log('[Electron] 优雅关闭超时，强制杀死进程');
        if (process.platform === 'win32') {
            const { exec } = require('child_process');
            exec(`taskkill /pid ${backendProcess.pid} /T /F`);
        } else {
            backendProcess.kill('SIGKILL');
        }
    }, 5000);  // 5秒超时
    
    axios.post('http://localhost:8000/api/v2/system/shutdown')
        .then(() => {
            clearTimeout(shutdownTimeout);
            console.log('[Electron] 后端已优雅关闭');
        })
        .catch((error) => {
            console.error('[Electron] 优雅关闭失败，将强制杀死:', error.message);
            // 超时处理器会强制杀死
        });
}
```

---

### 方案3：后端端 - 注册信号处理器（中等 ⭐⭐⭐）

**原理**：让后端能够捕获 `SIGTERM` 信号，在信号处理器中清理监控进程。

**修改位置**：`lifeprism/server/main.py`

**优点**：
- ✅ 不需要修改 Electron 端
- ✅ 能执行清理逻辑

**缺点**：
- ❌ Windows 上信号处理不可靠（Windows 信号机制与 Unix 不同）
- ❌ uvicorn 可能拦截信号
- ❌ PyInstaller 打包后信号处理可能失效
- ⚠️ 不如方案1/2可靠

**实现代码**：
```python
if __name__ == "__main__":
    import signal
    
    def cleanup_handler(signum, frame):
        logger.info(f"收到信号 {signum}，正在清理...")
        # 清理监控进程
        if hasattr(app.state, "monitor_process") and app.state.monitor_process:
            proc = app.state.monitor_process
            if proc.is_alive():
                proc.terminate()
                proc.join(timeout=3)
                if proc.is_alive():
                    proc.kill()
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, cleanup_handler)
    signal.signal(signal.SIGINT, cleanup_handler)
    
    # ... uvicorn.run()
```

---

### 方案4：监控进程端 - 心跳检测（备选 ⭐⭐⭐）

**原理**：监控进程定期检测父进程（后端）是否存活，如果父进程死亡则自动退出。

**修改位置**：`lifeprism/monitor/windows_monitor/main.py`

**优点**：
- ✅ 防御性编程（即使父进程异常退出也能清理）
- ✅ 不依赖 Electron 或后端的清理逻辑
- ✅ 适用于所有异常退出场景

**缺点**：
- ⚠️ 增加监控进程复杂度
- ⚠️ 有延迟（心跳间隔，通常5秒）
- ⚠️ 需要额外依赖（psutil）

**实现代码**：
```python
def main():
    import os
    import psutil
    import threading
    import time
    
    parent_pid = os.getppid()  # 获取父进程PID
    
    def check_parent_alive():
        """检查父进程是否存活"""
        try:
            parent = psutil.Process(parent_pid)
            return parent.is_running()
        except psutil.NoSuchProcess:
            return False
    
    runtime = build_monitor_runtime()
    
    # 启动心跳检测线程
    def heartbeat():
        while True:
            time.sleep(5)  # 每5秒检测一次
            if not check_parent_alive():
                logger.warning("检测到父进程已退出，监控进程自动退出")
                runtime.stop()
                sys.exit(0)
    
    threading.Thread(target=heartbeat, daemon=True).start()
    
    # ... 原有逻辑
```

---

## 推荐方案

### 短期方案（立即修复）

**采用方案1**：使用进程树杀死
- 改动最小，立即生效
- 彻底解决孤儿进程问题

### 长期方案（架构优化）

**方案2 + 方案4 组合**：
1. **主要依靠方案2**：正常情况下优雅关闭，后端正确清理监控进程
2. **方案4作为保险**：即使优雅关闭失败，监控进程也能自动检测并退出

这样既保证了正常流程的优雅性，又有防御性措施防止孤儿进程。

---

## 触发条件

满足以下**所有条件**时会触发此 bug：

1. ✅ Windows 系统
2. ✅ 使用 PyInstaller 打包（`app.isPackaged == true`）
3. ✅ 配置 `monitor_type = "lifeprism"`（启用内置监控）
4. ✅ 从托盘菜单选择"退出 LifePrism"
5. ❌ Electron 使用 `backendProcess.kill()` 强制杀死后端

**不会触发的情况**：
- Linux/macOS 系统（进程管理机制不同）
- 开发环境（通常使用 Ctrl+C 优雅退出）
- 不启用监控（没有子进程）

---

## 影响范围

| 环境 | 是否受影响 | 原因 |
|------|-----------|------|
| Windows 打包环境 | ✅ 是 | `backendProcess.kill()` 不杀子进程 |
| Windows 开发环境 | ❌ 否 | Ctrl+C 触发优雅关闭 |
| Linux 打包环境 | ⚠️ 可能 | 取决于进程管理方式 |
| macOS 打包环境 | ⚠️ 可能 | 取决于进程管理方式 |

---

## 相关 Bug

- `docs/history-bugs/2026-04-22-multiprocessing-infinite-loop.md`：监控子进程导致的无限启动循环（已修复）
  - 该 bug 是监控进程**启动时**的问题
  - 本 bug 是监控进程**退出时**的问题
  - 两者都与 Windows 的 multiprocessing 机制有关

---

## 诊断方法

### 1. 检查进程是否残留

**Windows 任务管理器**：
1. 退出 LifePrism
2. 打开任务管理器（Ctrl + Shift + Esc）
3. 查看"详细信息"选项卡
4. 搜索 `python` 或 `lifeprism`

**正常情况**：所有相关进程都已退出
**异常情况**：仍有 Python 进程在运行

### 2. 使用命令行检查

```bash
# 查看所有 Python 进程
tasklist | findstr python

# 查看所有 lifeprism 进程
tasklist | findstr lifeprism
```

### 3. 检查日志

查看 `localData/debug_logs/electron.log`：

**正常日志**（优雅关闭）：
```
[Electron] 应用即将退出...
[Electron] 正在关闭后端进程...
[Backend] 正在终止监控进程 (PID: xxxxx)...
[Backend] 监控进程已清理
[Backend] 进程退出，代码: 0
```

**异常日志**（强制杀死）：
```
[Electron] 应用即将退出...
[Electron] 正在关闭后端进程...
[Backend] 进程退出，代码: 1
# 缺少监控进程清理日志
```

---

## 经验教训

1. **进程管理的平台差异**：Windows 和 Unix 的进程管理机制不同，需要针对性处理
2. **子进程清理的重要性**：父进程退出时必须确保所有子进程也被清理
3. **优雅关闭 vs 强制杀死**：优雅关闭能执行清理逻辑，强制杀死可能留下孤儿进程
4. **防御性编程**：子进程应该有自我保护机制（如心跳检测），防止变成孤儿进程

---

## 更新记录

- **2026-04-22**：发现 bug，完成根因分析，提出4种修复方案，待实施方案1
