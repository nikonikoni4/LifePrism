# 数据源选择 UI 设计

## 概述

在"存储与数据源"设置页面中添加"数据源选择"选项，让用户在 lifeprism 内置监控和 ActivityWatch 之间切换数据源。

## 需求

- 在"LifePrism 数据路径"下方添加"数据源选择"单选组件
- 两个选项横排显示（参考"截图频率等级"样式）
  - A: lifeprism 内置监控（只有开启 lifeprism 内置监控才能开启截图监控）
  - B: 使用 activitywatch（需要额外安装）
- 选择 B 时显示 ActivityWatch 数据库路径选择器
- 选择 A 时隐藏 ActivityWatch 数据库路径选择器
- 默认选择 lifeprism 内置监控

## UI 设计

### 布局位置

在 `SettingsApp.tsx` 的"存储与数据源"部分，"LifePrism 数据路径"和"ActivityWatch 数据库路径"之间：

```
存储与数据源
├── 配置文件路径
├── LifePrism 数据路径
├── [新增] 数据源选择
│   ├── ○ lifeprism 内置监控
│   │      只有开启 lifeprism 内置监控才能开启截图监控
│   └── ○ 使用 activitywatch（需要额外安装）
└── ActivityWatch 数据库路径  ← conditional visibility
```

### 组件样式

使用与"截图频率等级"相同的 radio button 样式：

```tsx
<label className="flex items-start gap-3 p-4 bg-gray-50 rounded-xl border border-gray-100 cursor-pointer hover:border-blue-300 transition-all">
    <input type="radio" name="monitorSource" value="lifeprism" />
    <div>
        <div className="text-sm font-bold text-slate-700">lifeprism 内置监控</div>
        <div className="text-xs text-slate-400 mt-1">只有开启 lifeprism 内置监控才能开启截图监控</div>
    </div>
</label>
```

## 交互逻辑

### State 管理

- 新增 state: `monitorType`（初始值从 `settings.monitor_type` 加载）
- 新增 state: `showAwPath`（根据 `monitorType` 计算，`monitorType === 'activitywatch'` 时为 true）

### 自动保存

选择变化时调用 `triggerAutoSave({ monitor_type: newType })`

### 条件显示

ActivityWatch 数据库路径选择器根据 `showAwPath` 显示/隐藏：

```tsx
{showAwPath && (
    <div>
        <label>ActivityWatch 数据库路径</label>
        {/* 现有输入框和按钮 */}
    </div>
)}
```

### 截图监控联动

在"截图监控"部分的开关键增加条件：

```tsx
disabled={monitorType !== 'lifeprism' || !modelName}
```

当 `monitorType !== 'lifeprism'` 时，截图监控开关自动禁用。

## 实现文件

- `frontend/apps/settings/SettingsApp.tsx`
  - 添加 `monitorType` state（在 `awPath` state 附近）
  - 添加"数据源选择"radio button 组
  - 修改 ActivityWatch 数据库路径的条件显示
  - 修改截图监控开关的 disabled 条件

## 配置字段

- `monitor_type`: `'lifeprism'` | `'activitywatch'`
- 已有迁移脚本 `s002_add_monitor_type.py` 定义了默认值 `'lifeprism'`
