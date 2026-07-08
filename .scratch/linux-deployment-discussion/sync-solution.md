# Linux 部署与数据同步方案讨论记录

**讨论时间**: 2026-07-08  
**状态**: 待定（P2）

---

## 部署需求

### 三种运行形态

1. **Windows 桌面完整版** (`main.py`)
   - FastAPI + Electron 前端 + Agent + Monitor
   - 主要使用场景

2. **Linux Web Demo** (`main_web_demo.py`)
   - FastAPI + 静态前端 + Agent（无 Monitor）
   - Nginx 反向代理
   - 用于演示与远程访问

3. **Linux Agent Only** (`main_agent_only.py`)
   - 仅 Agent Loop + Channel（无 FastAPI，无前端，无 Monitor）
   - 微信渠道服务
   - 服务器后台运行

---

## 已明确的决策

### 1. 架构方案
- **多入口架构**: 三个独立启动文件，不用 if/else 配置
- **Monitor 模块**: 延迟导入（`if sys.platform == "win32"`），Linux 不导入
- **路径系统**: 保持现有逻辑，Linux 也用 `config.yaml` 的 `lifeprism_data_path`

### 2. 使用模式
- **主备模式**: 不会同时使用 Windows 和 Linux
- **平时用 Windows**: 在家/办公室
- **出门用 Linux Agent**: 通过微信对话

### 3. 同步方案基本框架
- **同步方向**: 双向（Windows ↔ Linux）
- **同步时机**: 启动时立即同步 + 定时同步（10 分钟）
- **通信方式**: Windows 主动拉取 + 推送，Linux 被动响应
- **数据加密**:
  - 数据库文件: SQLCipher（AES-256）
  - 传输: HTTPS/TLS
  - 认证: API Key

### 4. 同步范围
**需要同步的表**:
- Monitor 采集: `window_events`, `user_app_behavior_log`, `behavior_analysis`
- 用户输入: `mood_entries`, `timeline_custom_block`, `diary`, `todo_list`, `custom_record_*`
- 元数据: `category`, `sub_category`, `goal`, `habits`
- 缓存表: `*_cache`

**不需要同步**:
- `screen_captures` (截图资源，太大)
- `tokens_usage_log` (日志类)

---

## 核心争议点：冲突处理

### 最初方案（被否决 - 改动太大）
- 所有表增加 3 个字段：`version`, `device_id`, `updated_at`
- 理由：版本号冲突检测，不依赖时钟同步
- 问题：30+ 张表都要改 schema，改动量巨大

### 简化方案（待评估）
**只用现有的 `updated_at` 字段，零改动**

**核心逻辑**:
```
1. 拉取: WHERE updated_at > 上次同步时间
2. 写入: INSERT OR REPLACE (相同 ID 覆盖)
3. 无版本号、无设备 ID
```

**支持理由**:
- 主备模式，不会同时修改同一条记录
- Linux Agent 只有 AI 工具写入，频率低
- 冲突概率 < 0.1%
- NTP 自动时钟同步，误差通常 < 1 秒
- 零改动，快速验证

**风险**:
- 时钟不同步可能漏数据（但下次同步会补）
- 极端情况同一记录冲突（但几乎不会发生）

---

## 真实冲突场景分析

### 场景 1：同一条记录被修改
**会发生吗?** ❌ 几乎不会

原因：用户不会记住记录 ID，不会在两端同时修改同一条数据

### 场景 2：不同记录，时间戳问题
**会有问题吗?** ❌ 不会

原因：不同 ID 不会互相覆盖，两条记录都存在

### 场景 3：时钟不同步
**会有问题吗?** ⚠️ 理论上会，但影响很小

最坏情况：可能漏掉刚写入的数据，但下次同步（10 分钟后）会补齐

---

## 待决策问题

1. **是否接受 `updated_at` 零改动方案？**
2. **10 分钟同步间隔是否合适？**
3. **SQLCipher 加密方案是否可行？**
4. **API Key 认证是否足够？**

---

## 参考资料

### 成熟的双向同步方案
- **PouchDB/CouchDB**: MVCC + 增量同步，但是 NoSQL（我们用 SQLite）
- **SQLite DBSync**: 商业方案，支持增量同步 + 加密，需付费

### 数据库加密
- **SQLCipher**: 开源免费，AES-256，透明加密
- **SQLite SEE**: 官方方案，$2000，功能与 SQLCipher 类似

---

## 下一步

1. 确认冲突处理方案（零改动 vs 版本号）
2. 实现基础同步逻辑验证
3. 集成 SQLCipher 加密
4. 配置 HTTPS
