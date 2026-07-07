# 前端配置持久化与三层自适应模板系统

**Triage labels**: `ready-for-agent`
**Parent**: `.scratch/custom-records-module/PRD.md`
**Status**: `ready-for-agent`
**UI 原型**: `.scratch/custom-records-module/prototype.html`（打开后进入任意类型详情页，点击顶部"模板选择器"切换模板，点击"字段展示设置"打开弹窗配置字段角色）

## What to build

在卡片视图（L1 自动布局）就位后，实现完整的**展示配置系统**：用户可以为每个类型选择视觉模板（5 种），为每个字段指定展示角色（覆盖自动识别），配置保存到数据库后换设备仍生效。

端到端行为：
1. 用户在类型详情页点击"模板选择器"，实时预览 5 种卡片风格
2. 用户点击"字段展示设置"，在弹窗中为每个字段选择角色（title/main/chip/hidden/auto）
3. 配置修改后自动保存（debounce 500ms），刷新页面后配置仍然生效
4. 提供"模板对比"Tab，同一条数据在 5 种模板下并排展示

### 后端 Schema 变更

在现有 meta 表上增加字段（不新建配置表）：

- `custom_record_types` 增加:
  - `card_template` TEXT NOT NULL DEFAULT 'clean' — 卡片模板（clean|paper|minimal|bold|metric）
  - `icon` TEXT NOT NULL DEFAULT 'fileText' — 类型图标名
  - `accent_color` TEXT NOT NULL DEFAULT 'blue' — 强调色

- `custom_record_fields` 增加:
  - `display_role` TEXT NOT NULL DEFAULT 'auto' — 字段展示角色（auto|title|main|chip|hidden）

新增 API 端点：
- `PATCH /api/v2/custom-records/types/{type_id}` — 更新类型配置（template/icon/accent）
- `PATCH /api/v2/custom-records/types/{type_id}/fields/{field_id}` — 更新字段 display_role

### 前端 L2 字段角色配置

- "字段展示设置"弹窗：列出该类型所有字段
- 每个字段 5 选 1：auto / title / main / chip / hidden
- 用字段哈希色作为选中状态的高亮色
- "恢复自动"按钮一键重置所有字段为 auto
- 保存后关闭弹窗，卡片实时刷新

### 前端 L3 视觉模板系统

5 套模板 CSS，通过 `.tpl-{name}` 类名前缀控制视觉属性：

| 模板 | 核心视觉差异 |
|------|-------------|
| **clean** | 白底圆角、左侧竖条 accent、标准 chips |
| **paper** | 暖米色背景、衬线字体、顶部渐变条、虚线分割 |
| **minimal** | 透明背景、细线分割、去 chips 色块 |
| **bold** | accent 渐变填充背景、白字、半透明 chips |
| **metric** | chips 变为网格指标卡（label 上 value 下） |

模板选择器：顶部横向按钮组，选中项有动画指示器。

### 模板对比展示

"模板对比"Tab：使用同一条记录数据，并排渲染 5 个 EntryCard（分别强制指定 5 种模板），方便用户直观对比。

## Acceptance criteria

- [ ] 后端：`custom_record_types` 表增加 `card_template`、`icon`、`accent_color` 三个字段
- [ ] 后端：`custom_record_fields` 表增加 `display_role` 字段
- [ ] 后端：新增 `PATCH /custom-records/types/{type_id}` 更新类型配置
- [ ] 后端：新增 `PATCH /custom-records/types/{type_id}/fields/{field_id}` 更新字段角色
- [ ] 前端：类型详情页顶部显示模板选择器，切换后卡片实时刷新
- [ ] 前端：5 套模板 CSS 实现完整的视觉差异（背景、字体、chips 样式、accent 位置）
- [ ] 前端："字段展示设置"弹窗实现，每个字段 5 选 1
- [ ] 前端：字段角色覆盖后，L1 引擎以用户配置优先
- [ ] 前端：配置修改后自动保存（debounce），有保存成功提示
- [ ] 前端："模板对比"Tab 可并排查看同数据在 5 种模板下的效果
- [ ] 旧数据兼容：已有类型的配置字段使用 DEFAULT 值，无需迁移

## Blocked by

- `.scratch/custom-records-module/issues/05-frontend-card-view.md`（卡片视图和 EntryCard 组件必须先就位）
