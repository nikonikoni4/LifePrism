---
title: 扩展数据文件夹功能设计
date: 2026-05-05
status: draft
version: 1.0
---

# 扩展数据文件夹功能设计

## 1. 概述

### 1.1 功能目标

在 Add-on 界面增加扩展数据文件夹管理模块，允许用户添加自定义的额外数据文件夹（如读书笔记、个人文章等），并标记是否启用 AI 索引。

### 1.2 核心需求

- 用户可以添加、编辑、删除扩展文件夹配置
- 每个文件夹包含：名称、路径、描述、AI索引开关
- 使用文件夹选择器选择路径
- 数据持久化到 JSON 文件
- 删除操作仅删除配置，不删除磁盘文件

## 2. 整体架构

### 2.1 技术栈

- 后端：Python + FastAPI + JSON 文件存储
- 前端：React + TypeScript + Tailwind CSS
- 通信：RESTful API

### 2.2 数据流向

```
前端 AddonsApp.tsx 
  ↓ HTTP 请求
后端 add_on_api.py (FastAPI 路由)
  ↓ 调用
add_on_service.py (业务逻辑)
  ↓ 读写
expand_meta_data.json (数据持久化)
```

### 2.3 文件组织

**后端：**
- `lifeprism/server/api/add_on_api.py` - API 路由层
- `lifeprism/server/services/add_on_service.py` - 业务逻辑层
- `lifeprism/server/schemas/add_on_schemas.py` - 数据模型定义
- `{lifeprism_data_path}/expand_dir/expand_meta_data.json` - 数据存储

**前端：**
- `frontend/apps/addons/AddonsApp.tsx` - 主界面（扩展现有组件）
- `frontend/apps/addons/components/ExpandDirManager.tsx` - 扩展文件夹管理组件（新增）
- `frontend/apps/addons/api.ts` - API 调用封装（新增）
- `frontend/apps/addons/types.ts` - TypeScript 类型定义（新增）

## 3. 数据模型设计

### 3.1 JSON 数据结构

**文件路径：** `{lifeprism_data_path}/expand_dir/expand_meta_data.json`

```json
{
  "expand_dirs": [
    {
      "id": "1",
      "name": "读书笔记",
      "path": "D:/Documents/ReadingNotes",
      "description": "个人读书笔记和摘录",
      "ai_index": true,
      "created_at": "2026-05-05T10:30:00Z"
    },
    {
      "id": "2",
      "name": "工作文档",
      "path": "D:/Work/Documents",
      "description": "",
      "ai_index": false,
      "created_at": "2026-05-05T11:00:00Z"
    }
  ]
}
```

### 3.2 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | 唯一标识符，数字字符串，从 "1" 开始自增 |
| name | string | 是 | 文件夹名称 |
| path | string | 是 | 文件夹绝对路径 |
| description | string | 是 | 文件夹描述（可为空字符串） |
| ai_index | boolean | 是 | 是否启用 AI 索引 |
| created_at | string | 是 | 创建时间（ISO 8601 格式） |

### 3.3 后端 Schemas

**文件：** `lifeprism/server/schemas/add_on_schemas.py`

```python
from pydantic import BaseModel, Field
from typing import List
from datetime import datetime

class ExpandDirBase(BaseModel):
    name: str = Field(..., description="文件夹名称")
    path: str = Field(..., description="文件夹路径")
    description: str = Field(..., description="文件夹描述")
    ai_index: bool = Field(..., description="是否启用AI索引")

class ExpandDirCreate(ExpandDirBase):
    """创建扩展文件夹的请求模型"""
    pass

class ExpandDirUpdate(ExpandDirBase):
    """更新扩展文件夹的请求模型"""
    pass

class ExpandDirResponse(ExpandDirBase):
    """扩展文件夹的响应模型"""
    id: str = Field(..., description="唯一标识符（数字字符串）")
    created_at: datetime = Field(..., description="创建时间")

class ExpandDirListResponse(BaseModel):
    """扩展文件夹列表响应"""
    expand_dirs: List[ExpandDirResponse]
```

### 3.4 前端 Types

**文件：** `frontend/apps/addons/types.ts`

```typescript
export interface ExpandDir {
  id: string;
  name: string;
  path: string;
  description: string;
  ai_index: boolean;
  created_at: string;
}

export interface ExpandDirCreate {
  name: string;
  path: string;
  description: string;
  ai_index: boolean;
}

export interface ExpandDirListResponse {
  expand_dirs: ExpandDir[];
}
```

## 4. API 接口设计

### 4.1 路由定义

**文件：** `lifeprism/server/api/add_on_api.py`

```python
from fastapi import APIRouter, HTTPException
from lifeprism.server.schemas.add_on_schemas import (
    ExpandDirCreate,
    ExpandDirUpdate,
    ExpandDirResponse,
    ExpandDirListResponse,
)
from lifeprism.server.services import add_on_service

router = APIRouter(prefix="/api/v2/add_on", tags=["Add-on - 扩展功能"])

@router.get("/expand_dir", response_model=ExpandDirListResponse)
async def get_expand_dirs():
    """获取所有扩展数据文件夹"""
    expand_dirs = add_on_service.get_all_expand_dirs()
    return ExpandDirListResponse(expand_dirs=expand_dirs)

@router.post("/expand_dir", response_model=ExpandDirResponse, status_code=201)
async def create_expand_dir(data: ExpandDirCreate):
    """创建新的扩展数据文件夹"""
    return add_on_service.create_expand_dir(data)

@router.patch("/expand_dir/{id}", response_model=ExpandDirResponse)
async def update_expand_dir(id: str, data: ExpandDirUpdate):
    """更新扩展数据文件夹配置"""
    return add_on_service.update_expand_dir(id, data)

@router.delete("/expand_dir/{id}", status_code=204)
async def delete_expand_dir(id: str):
    """删除扩展数据文件夹配置（仅删除配置，不删除磁盘文件）"""
    add_on_service.delete_expand_dir(id)
```

### 4.2 API 端点说明

| 方法 | 路径 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| GET | `/api/v2/add_on/expand_dir` | 获取所有扩展文件夹 | - | `ExpandDirListResponse` |
| POST | `/api/v2/add_on/expand_dir` | 创建扩展文件夹 | `ExpandDirCreate` | `ExpandDirResponse` (201) |
| PATCH | `/api/v2/add_on/expand_dir/{id}` | 更新扩展文件夹 | `ExpandDirUpdate` | `ExpandDirResponse` |
| DELETE | `/api/v2/add_on/expand_dir/{id}` | 删除扩展文件夹 | - | 204 No Content |

### 4.3 API 行为

**GET `/api/v2/add_on/expand_dir`**
- 返回所有扩展文件夹配置列表
- 如果文件不存在，返回空列表
- 按 ID 升序排列

**POST `/api/v2/add_on/expand_dir`**
- 验证路径有效性（存在且可访问）
- 检查路径是否重复
- 生成新 ID（当前最大 ID + 1）
- 生成创建时间
- 保存到 JSON 文件
- 返回完整对象（包含 ID 和 created_at）

**PATCH `/api/v2/add_on/expand_dir/{id}`**
- 验证 ID 是否存在
- 如果修改了 path，验证新路径有效性
- 更新指定字段
- 保存到 JSON 文件
- 返回更新后的完整对象

**DELETE `/api/v2/add_on/expand_dir/{id}`**
- 验证 ID 是否存在
- 从 JSON 中删除该记录
- 不删除磁盘上的实际文件夹
- 返回 204 No Content

## 5. 业务逻辑层设计

### 5.1 Service 层职责

**文件：** `lifeprism/server/services/add_on_service.py`

**核心功能：**

1. **JSON 文件管理**
   - 读取 JSON 文件，如果不存在返回空列表
   - 写入 JSON 文件，使用原子性写入（临时文件 + rename）
   - 首次访问时自动创建目录和文件

2. **CRUD 操作**
   - `get_all_expand_dirs() -> List[ExpandDirResponse]`
   - `create_expand_dir(data: ExpandDirCreate) -> ExpandDirResponse`
   - `update_expand_dir(id: str, data: ExpandDirUpdate) -> ExpandDirResponse`
   - `delete_expand_dir(id: str) -> None`

3. **路径验证**
   - `validate_path(path: str) -> bool`
   - 检查路径是否存在
   - 检查路径是否可访问

4. **ID 生成**
   - `generate_next_id(existing_dirs: List[dict]) -> str`
   - 从 "1" 开始自增
   - 删除后不重用

### 5.2 ID 生成逻辑

```python
def generate_next_id(existing_dirs: List[dict]) -> str:
    """生成下一个 ID（数字字符串，从 1 开始自增）"""
    if not existing_dirs:
        return "1"
    
    # 提取所有数字 ID，找到最大值
    max_id = 0
    for item in existing_dirs:
        try:
            num = int(item["id"])
            max_id = max(max_id, num)
        except ValueError:
            continue
    
    # 返回下一个 ID
    return str(max_id + 1)
```

**特点：**
- 从 "1" 开始：`"1"` → `"2"` → `"3"` → `"10"` → `"100"`
- 纯数字字符串
- 严格递增，删除后不重用

### 5.3 数据文件位置

- 通过 `settings.lifeprism_data_path` 获取基础路径
- 完整路径：`{lifeprism_data_path}/expand_dir/expand_meta_data.json`
- 首次访问时自动创建目录和文件

### 5.4 原子性写入

```python
import json
import tempfile
from pathlib import Path

def save_data(data: dict, file_path: Path):
    """原子性写入 JSON 文件"""
    # 写入临时文件
    temp_fd, temp_path = tempfile.mkstemp(
        dir=file_path.parent,
        suffix='.tmp'
    )
    try:
        with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # 原子性重命名
        os.replace(temp_path, file_path)
    except Exception:
        # 清理临时文件
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise
```

## 6. 前端界面设计

### 6.1 组件结构

```
AddonsApp.tsx (主容器)
  ├─ 现有的浮窗插件卡片区域
  └─ ExpandDirManager.tsx (新增扩展文件夹管理区域)
       ├─ 标题 + "+" 按钮
       ├─ 文件夹卡片列表
       └─ 每个卡片包含：
            ├─ 名称输入框
            ├─ 描述输入框
            ├─ 路径显示 + 选择按钮
            ├─ AI索引开关 (on/off)
            └─ 删除按钮
```

### 6.2 交互流程

**1. 创建新文件夹：**
- 点击 "+" 按钮 → 在列表顶部插入一个空白可编辑卡片
- 默认值：`name=""`, `path=""`, `description=""`, `ai_index=false`
- 用户填写名称和描述
- 点击路径选择按钮 → 调用 `window.electronAPI.selectDirectory()`
- 选择路径后自动填充到输入框
- 失焦或点击保存 → 调用 POST API
- 成功后更新卡片显示 ID 和 created_at

**2. 编辑文件夹：**
- 直接在卡片上修改字段（name、description、path、ai_index）
- 失焦时自动调用 PATCH API 保存
- 保存失败时恢复原值并显示错误提示

**3. 删除文件夹：**
- 点击删除按钮 → 调用 DELETE API
- 成功后从列表中移除卡片
- 显示成功提示

### 6.3 UI 风格

**参考设计：**
- 整体风格参考 `SettingsApp.tsx`
- 配色方案使用 AddonsApp 的翠绿色系

**样式规范：**
- Section 容器：`bg-white rounded-[2rem] border border-gray-100 p-8 shadow-sm`
- 输入框：`bg-gray-50 border border-transparent focus:bg-white focus:border-emerald-200 focus:ring-4 focus:ring-emerald-50/50 rounded-xl px-4 py-3`
- 标签：`text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 block`
- 按钮：`bg-emerald-500 hover:bg-emerald-600 text-white rounded-xl px-4 py-2`
- 开关：参考 settings 的 toggle 样式，使用 emerald 配色

**配色方案：**
- 主色：`emerald-500` / `teal-600`
- 背景渐变：`from-emerald-50 to-teal-100`
- 边框高亮：`border-emerald-300`
- 成功状态：`green-500`
- 错误状态：`red-500`

**图标：**
- 使用 `lucide-react` 图标库
- Section 标题：`FolderOpen` 或 `FolderPlus`
- 路径选择按钮：`FolderSearch`
- 删除按钮：`Trash2`
- 添加按钮：`Plus`

### 6.4 前端 API 封装

**文件：** `frontend/apps/addons/api.ts`

```typescript
import { ExpandDir, ExpandDirCreate, ExpandDirListResponse } from './types';

const BASE_URL = '/api/v2/add_on';

export const AddOnAPI = {
  async getExpandDirs(): Promise<ExpandDir[]> {
    const response = await fetch(`${BASE_URL}/expand_dir`);
    if (!response.ok) throw new Error('获取扩展文件夹失败');
    const data: ExpandDirListResponse = await response.json();
    return data.expand_dirs;
  },

  async createExpandDir(data: ExpandDirCreate): Promise<ExpandDir> {
    const response = await fetch(`${BASE_URL}/expand_dir`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || '创建失败');
    }
    return response.json();
  },

  async updateExpandDir(id: string, data: ExpandDirCreate): Promise<ExpandDir> {
    const response = await fetch(`${BASE_URL}/expand_dir/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || '更新失败');
    }
    return response.json();
  },

  async deleteExpandDir(id: string): Promise<void> {
    const response = await fetch(`${BASE_URL}/expand_dir/${id}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || '删除失败');
    }
  },
};
```

## 7. 错误处理与边界情况

### 7.1 后端错误处理

**路径验证失败：**
- 路径不存在 → 400 Bad Request: `"路径不存在: {path}"`
- 路径无访问权限 → 400 Bad Request: `"无法访问路径: {path}"`

**ID 不存在：**
- PATCH/DELETE 时 ID 不存在 → 404 Not Found: `"扩展文件夹不存在: {id}"`

**JSON 文件问题：**
- 文件损坏无法解析 → 记录日志，返回空列表
- 写入失败 → 500 Internal Server Error: `"保存配置失败"`

**重复路径检查：**
- 创建/更新时检查是否已存在相同路径
- 如果存在 → 400 Bad Request: `"该路径已被添加"`

**必填字段验证：**
- name、path、ai_index 为空 → 422 Unprocessable Entity（Pydantic 自动验证）

### 7.2 前端错误处理

**API 调用失败：**
- 使用 `toast.error()` 显示错误信息
- 创建失败 → 移除临时卡片
- 更新失败 → 恢复原值

**路径选择取消：**
- 用户取消选择 → 保持原路径不变

**必填字段验证：**
- name、path 为空时禁用保存
- 显示提示信息："请填写必填字段"

**网络错误：**
- 请求超时或网络断开 → 显示 "网络错误，请重试"

### 7.3 边界情况

**首次使用：**
- `expand_dir` 目录不存在 → 自动创建
- JSON 文件不存在 → 返回空列表 `{"expand_dirs": []}`

**并发写入：**
- 使用原子性写入（临时文件 + rename）避免数据损坏

**空列表：**
- 显示空状态提示："暂无扩展文件夹，点击 + 添加"

**路径选择器：**
- 仅在 Electron 环境下可用
- Web 环境下禁用路径选择按钮，显示提示："仅桌面版可用"

## 8. 测试策略

### 8.1 后端测试

**Service 层单元测试：**
- ID 生成逻辑（空列表、有数据、删除后）
- CRUD 操作（创建、读取、更新、删除）
- 路径验证（存在/不存在/无权限）
- JSON 文件读写（文件不存在、损坏、并发）
- 重复路径检查

**API 集成测试：**
- GET 返回正确的列表
- POST 创建成功并返回完整对象
- PATCH 更新成功
- DELETE 删除成功
- 各种错误场景（400/404/422/500）

### 8.2 前端测试

**手动测试场景：**
- 创建第一个文件夹
- 编辑文件夹信息（名称、描述、路径）
- 切换 AI 索引开关
- 删除文件夹
- 路径选择器交互
- 错误提示显示

**边界测试：**
- 空列表状态
- 创建时取消路径选择
- 网络请求失败
- 必填字段为空
- 路径不存在
- 重复路径

### 8.3 测试数据

```json
{
  "expand_dirs": [
    {
      "id": "1",
      "name": "读书笔记",
      "path": "D:/Documents/ReadingNotes",
      "description": "个人读书笔记和摘录",
      "ai_index": true,
      "created_at": "2026-05-05T10:30:00Z"
    },
    {
      "id": "2",
      "name": "工作文档",
      "path": "D:/Work/Documents",
      "description": "",
      "ai_index": false,
      "created_at": "2026-05-05T11:00:00Z"
    },
    {
      "id": "3",
      "name": "个人文章",
      "path": "D:/Writing/Articles",
      "description": "个人博客文章和草稿",
      "ai_index": true,
      "created_at": "2026-05-05T12:00:00Z"
    }
  ]
}
```

## 9. 实现步骤

### 9.1 后端实现顺序

1. 创建 `add_on_schemas.py` - 定义数据模型
2. 创建 `add_on_service.py` - 实现业务逻辑
   - JSON 文件读写
   - ID 生成
   - 路径验证
   - CRUD 操作
3. 创建 `add_on_api.py` - 实现 API 路由
4. 在 `main.py` 中注册路由
5. 编写单元测试和集成测试

### 9.2 前端实现顺序

1. 创建 `types.ts` - 定义 TypeScript 类型
2. 创建 `api.ts` - 封装 API 调用
3. 创建 `ExpandDirManager.tsx` - 实现管理组件
   - 列表渲染
   - 创建功能
   - 编辑功能
   - 删除功能
   - 路径选择器
4. 在 `AddonsApp.tsx` 中集成组件
5. 手动测试各项功能

### 9.3 集成测试

1. 启动后端服务
2. 启动前端开发服务器
3. 测试完整流程：创建 → 编辑 → 删除
4. 测试错误场景
5. 验证数据持久化

## 10. 注意事项

### 10.1 路径处理

- Windows 路径使用反斜杠 `\`，需要正确处理
- 路径验证时使用 `Path.exists()` 和 `Path.is_dir()`
- 前端显示路径时保持原格式

### 10.2 数据一致性

- 使用原子性写入避免数据损坏
- 读取 JSON 失败时返回空列表，不中断服务
- 记录详细日志便于排查问题

### 10.3 用户体验

- 自动保存，减少用户操作
- 失败时显示清晰的错误提示
- 空状态时显示引导信息
- 加载状态显示 loading 动画

### 10.4 扩展性

- ai_index 字段当前仅存储状态，不触发任何操作
- 为未来 AI 索引功能预留接口
- JSON 结构易于扩展新字段

## 11. 未来扩展

### 11.1 AI 索引功能

- 当 ai_index 为 true 时，触发文件夹内容索引
- 支持文件类型过滤（.md, .txt, .pdf 等）
- 支持增量索引和全量索引
- 提供索引进度显示

### 11.2 文件夹监控

- 监控文件夹变化（新增、修改、删除文件）
- 自动触发增量索引
- 显示最后更新时间

### 11.3 批量操作

- 批量启用/禁用 AI 索引
- 批量删除
- 导入/导出配置

### 11.4 统计信息

- 显示文件夹大小
- 显示文件数量
- 显示索引状态

---

**设计完成日期：** 2026-05-05  
**设计版本：** 1.0  
**设计状态：** 待审查

