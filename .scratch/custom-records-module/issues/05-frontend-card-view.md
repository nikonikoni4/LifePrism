# 前端卡片视图与自适应布局引擎

**Triage labels**: `completed`
**Parent**: `.scratch/custom-records-module/PRD.md`
**Status**: `completed`（TDD 完成，27 个纯函数测试通过，UI 人工验证通过）
**UI 原型**: `.scratch/custom-records-module/prototype.html`（打开后进入任意类型详情页，默认展示卡片视图；点击"模板对比"Tab 可查看多模板效果）

## What to build

在基础前端实现（类型列表 + 新建 + 表格详情）就位后，为类型详情页增加**卡片视图**作为默认展示方式，替代原有的纯表格视图。

端到端行为：
1. 用户进入某类型详情页，默认看到卡片视图（而非表格）
2. 每张卡片根据字段内容自动选择最佳布局（笔记式/条目式/速记式）
3. 卡片按日期分组，日期头部显示"今天/昨天/具体日期"
4. 用户可在"卡片"和"表格"两个 Tab 间切换视图
5. 卡片中字段颜色通过字段名哈希稳定分配，无需后端配置

### L1 启发式布局引擎

核心算法输入为 `fields[]` + `data{}`，输出为 `{ layout, title, main, chips }`。

- **字段角色识别优先级**: 用户覆盖 > 关键词匹配(title/main/hidden keywords) > 内容长度启发
- **布局模式**: `note`(有主体大段文字) / `compact`(键值对列表) / `tight`(纯标签云)
- 算法实现细节参考: `.scratch/custom-records-module/design-spec.md` §L1

### EntryCard 组件

- 支持三种布局渲染：note / compact / tight
- 左侧 accent 竖条（颜色来自类型 accent_color）
- 头部显示时间戳 + 布局类型标签（笔记/条目/速记）
- 主体区域：标题(如有) + 正文(如有) + chips 标签区
- hover 显示编辑/删除按钮
- 字段配色通过 `hashStr(field_key)` 稳定分配

### 卡片视图页面结构

- 按日期分组：同一天的记录归为一组
- 日期头部：左侧星期图标 + "今天/昨天/月日" + 日期字符串 + 记录数
- 网格布局：响应式 1~2 列
- 空状态：无记录时显示占位提示

## Acceptance criteria

- [x] 类型详情页默认展示卡片视图（Tab 栏"卡片"为默认选中）
- [x] EntryCard 组件实现三种布局（note/compact/tight）的正确渲染
- [x] L1 启发式引擎能正确识别常见字段角色（如含 "笔记/review/content" 的字段标记为 main）
- [x] 卡片按日期分组，日期头部显示正确（今天/昨天/具体日期）
- [x] 字段颜色通过 `field_key` 哈希稳定分配，同一字段跨记录颜色一致
- [x] 卡片 hover 显示删除按钮
- [x] Tab 切换"卡片"↔"表格"时有过渡动画
- [x] 空记录状态下显示友好的占位 UI
- [x] 对接已有后端 API：`GET /custom-records/{type_id}/entries`

## Blocked by

- `.scratch/custom-records-module/issues/04-frontend.md`（基础前端页面和路由必须先就位）
