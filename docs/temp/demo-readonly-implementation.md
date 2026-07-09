# Demo 只读模式完整实施方案

本文档记录了 LifePrism Demo 只读模式的完整实施方案，用于解决演示环境的恶意数据写入和多人并发问题。

## 一、方案概述

### 问题背景

1. **恶意数据污染**：用户可能写入不当内容，影响后续访客体验
2. **多人并发冲突**：无隔离机制，多人同时操作可能导致数据混乱
3. **API Key 泄露风险**：AI 聊天功能需要 API Key，有泄露风险

### 解决方案

| 措施 | 实现方式 | 效果 |
|------|----------|------|
| **后端只读拦截** | 中间件拦截所有写操作（POST/PUT/PATCH/DELETE） | ✅ 彻底禁止数据修改 |
| **前端引导弹窗** | 首次访问显示项目信息、投票链接、只读说明 | ✅ 引导用户了解项目 |
| **每日数据重置** | 凌晨 4 点自动删除旧数据并重新生成 | ✅ 保持演示环境干净 |

## 二、后端实施

### 2.1 配置项（settings_manager.py）

新增配置项：

```yaml
# config.yaml
demo_mode: false  # Demo 演示模式（只读模式，拦截所有写操作）
```

环境变量：

```bash
export LIFEPRISM_DEMO_MODE=true
```

优先级：**环境变量 > config.yaml**

### 2.2 只读中间件（main.py）

拦截规则：

- **拦截方法**：POST / PUT / PATCH / DELETE
- **例外路径**：/health（健康检查）
- **返回码**：403 Forbidden

响应示例：

```json
{
  "error_code": "DEMO_MODE_READ_ONLY",
  "message": "Demo 演示网站无法写入数据，请到本地部署或下载安装包",
  "details": {
    "github_url": "https://github.com/nikonikoni4/LifePrism",
    "vote_url": "https://forum.trae.cn/t/topic/70390",
    "hint": "您可以在 GitHub 下载安装包本地安装，或参与创造力大赛投票"
  }
}
```

### 2.3 启动方式

```bash
# 方式 1：环境变量
export LIFEPRISM_DEMO_MODE=true
uvicorn lifeprism.server.main:app --host 0.0.0.0 --port 8088

# 方式 2：修改 config.yaml
# demo_mode: true
uvicorn lifeprism.server.main:app --host 0.0.0.0 --port 8088
```

## 三、前端实施

### 3.1 环境变量配置（.env.demo）

```env
# 启用 Demo 模式
VITE_DEMO_MODE=true

# API 地址
VITE_API_BASE_URL=http://localhost:8088
```

### 3.2 引导弹窗（DemoDialog.tsx）

功能：

- ✅ 首次访问自动弹出
- ✅ 展示项目信息（GitHub 链接）
- ✅ 展示投票链接（创造力大赛）
- ✅ 只读限制说明
- ✅ "不再提示本次会话"选项

触发条件：

```typescript
// sessionStorage 控制，每次会话只弹一次
if (isDemoMode && !sessionStorage.getItem('demo-dialog-shown')) {
  setShowDemoDialog(true);
}
```

### 3.3 构建方式

```bash
cd frontend

# 开发环境
npm run dev

# Demo 模式构建
npm run build -- --mode demo
```

## 四、数据重置脚本

### 4.1 自动重置脚本（reset_demo_data.sh）

执行流程：

1. ✅ 停止 LifePrism 后端服务（SIGTERM → SIGKILL）
2. ✅ 删除 `localData` 目录
3. ✅ 重新生成演示数据（过去 7 天）
4. ✅ 重启后端服务（nohup 后台运行）

### 4.2 配置 Crontab

```bash
# 编辑 crontab
crontab -e

# 添加每天凌晨 4 点执行（替换路径为实际路径）
0 4 * * * cd /path/to/LifeWatch-AI && bash scripts/demo/reset_demo_data.sh >> /var/log/lifeprism-demo-reset.log 2>&1
```

### 4.3 验证

```bash
# 查看重置日志
tail -f /var/log/lifeprism-demo-reset.log

# 查看后端服务状态
ps aux | grep lifeprism.server.main

# 查看后端日志
tail -f /var/log/lifeprism-backend.log
```

## 五、部署流程

### 5.1 初始部署

```bash
# 1. 克隆代码
git clone https://github.com/nikonikoni4/LifePrism.git
cd LifePrism

# 2. 安装后端依赖
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. 生成初始演示数据
python scripts/demo/generate_demo_data.py --days 7 --force

# 4. 启动后端（Demo 模式）
export LIFEPRISM_DEMO_MODE=true
nohup uvicorn lifeprism.server.main:app --host 0.0.0.0 --port 8088 > /var/log/lifeprism-backend.log 2>&1 &

# 5. 构建前端（Demo 模式）
cd frontend
npm install
npm run build -- --mode demo

# 6. 配置 Nginx 反向代理（参考下方配置）

# 7. 配置自动重置
crontab -e
# 添加：0 4 * * * cd /path/to/LifePrism && bash scripts/demo/reset_demo_data.sh >> /var/log/lifeprism-demo-reset.log 2>&1
```

### 5.2 Nginx 配置示例

```nginx
server {
    listen 80;
    server_name demo.lifeprism.com;

    # 前端静态文件
    location / {
        root /path/to/LifePrism/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 代理
    location /api {
        proxy_pass http://127.0.0.1:8088;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

## 六、修改的文件清单

### 后端（4 个文件）

| 文件 | 修改内容 |
|------|----------|
| `lifeprism/config/settings_manager.py` | 新增 `demo_mode` 配置项和环境变量映射 |
| `lifeprism/server/main.py` | 新增 `demo_mode_middleware` 拦截写操作 |
| `scripts/demo/reset_demo_data.sh` | 新建数据重置脚本 |
| `scripts/demo/README.md` | 更新文档，补充 Demo 只读模式和数据重置说明 |

### 前端（4 个文件）

| 文件 | 修改内容 |
|------|----------|
| `frontend/src/config/env.ts` | 新建环境变量配置文件 |
| `frontend/src/components/DemoDialog.tsx` | 新建 Demo 引导弹窗组件 |
| `frontend/App.tsx` | 集成 DemoDialog，增加首次访问弹窗逻辑 |
| `frontend/.env.demo` | 新建 Demo 模式环境变量配置 |

## 七、测试清单

### 7.1 后端测试

```bash
# 1. 启动后端（Demo 模式）
export LIFEPRISM_DEMO_MODE=true
uvicorn lifeprism.server.main:app --host 0.0.0.0 --port 8088

# 2. 测试只读拦截（应返回 403）
curl -X POST http://localhost:8088/api/todos \
  -H "Content-Type: application/json" \
  -d '{"name": "测试任务"}'

# 预期响应：
# {
#   "error_code": "DEMO_MODE_READ_ONLY",
#   "message": "Demo 演示网站无法写入数据...",
#   ...
# }

# 3. 测试读操作（应正常返回）
curl http://localhost:8088/api/todos

# 4. 测试健康检查（例外路径，应正常返回）
curl http://localhost:8088/health
```

### 7.2 前端测试

```bash
# 1. 构建前端（Demo 模式）
cd frontend
npm run build -- --mode demo

# 2. 启动预览服务器
npm run preview

# 3. 访问 http://localhost:4173
#    - 应自动弹出引导弹窗
#    - 勾选"不再提示"后关闭，刷新页面不应再弹出
#    - 新开隐身窗口应再次弹出
```

### 7.3 数据重置测试

```bash
# 1. 手动执行重置脚本
bash scripts/demo/reset_demo_data.sh

# 2. 检查日志
cat /var/log/lifeprism-demo-reset.log

# 3. 验证数据已重置
ls -la localData/
```

## 八、注意事项

### ⚠️ 安全提示

1. **API Key 管理**：Demo 环境不启用 AI 聊天功能，避免 API Key 泄露
2. **数据隐私**：演示数据应使用虚构内容，避免包含真实个人信息
3. **访问频率限制**：建议在 Nginx 配置 rate limiting，防止恶意请求

### ⚠️ 运维提示

1. **日志监控**：定期检查 `/var/log/lifeprism-demo-reset.log` 和 `/var/log/lifeprism-backend.log`
2. **磁盘空间**：数据重置会产生临时文件，定期清理日志
3. **备份策略**：虽然是 Demo 环境，建议保留最近一次的数据备份

### ⚠️ 用户体验

1. **重置时段**：选择凌晨 4 点（流量低谷）进行重置
2. **服务中断**：重置期间服务不可用（约 30 秒），前端应显示友好提示
3. **公告提示**：建议在页面顶部显示"Demo 环境，每天凌晨 4 点自动重置"

## 九、常见问题

### Q1: 前端弹窗没有显示？

检查：
1. `.env.demo` 文件中 `VITE_DEMO_MODE=true` 是否正确
2. 构建时是否使用了 `--mode demo` 参数
3. 浏览器 sessionStorage 是否有 `demo-dialog-shown` 缓存（清除后重试）

### Q2: 后端仍然可以写入数据？

检查：
1. 环境变量 `LIFEPRISM_DEMO_MODE=true` 是否设置
2. `config.yaml` 中 `demo_mode: true` 是否配置
3. 中间件是否正确注册（查看启动日志）

### Q3: 数据重置失败？

检查：
1. `reset_demo_data.sh` 中的路径是否正确
2. 后端进程是否正确停止（`ps aux | grep lifeprism`）
3. `localData` 目录是否有写权限
4. Python 虚拟环境是否激活

### Q4: 如何临时禁用只读模式？

```bash
# 方式 1：不设置环境变量
unset LIFEPRISM_DEMO_MODE
uvicorn lifeprism.server.main:app --host 0.0.0.0 --port 8088

# 方式 2：修改 config.yaml
# demo_mode: false
```

## 十、相关资源

- **GitHub 仓库**：https://github.com/nikonikoni4/LifePrism
- **创造力大赛投票**：https://forum.trae.cn/t/topic/70390
- **详细文档**：`scripts/demo/README.md`
- **技术债务**：`docs/technical-debt/api-redundant-exception-handling.md`
