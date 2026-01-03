# LocalStorage 缓存使用指南

## 📚 概述

本项目已集成完整的 LocalStorage 缓存系统,用于缓存报告数据和用户设置,大幅提升应用性能和用户体验。

## 🎯 主要功能

### 1. 自动缓存管理
- ✅ **智能过期策略**: 当天数据缓存时间短,历史数据缓存时间长
- ✅ **自动清理**: 每小时自动清理过期缓存
- ✅ **版本控制**: 支持数据版本管理,自动失效旧版本缓存
- ✅ **存储监控**: 自动监控存储空间使用情况

### 2. 缓存过期时间

| 数据类型 | 当前数据 | 历史数据 |
|---------|---------|---------|
| 日报告 | 30 分钟 | 24 小时 |
| 周报告 | 1 小时 | 7 天 |
| 月报告 | 2 小时 | 30 天 |
| 用户设置 | - | 1 年 |

### 3. 已集成的 API

所有报告 API 已自动集成缓存:
- `ReportsAPI.getDailyReport()` - 日报告
- `ReportsAPI.getWeeklyReport()` - 周报告
- `ReportsAPI.getMonthlyReport()` - 月报告

## 💻 使用方法

### 基础使用 (已自动集成)

```typescript
// 1. 获取日报告 (自动使用缓存)
const dailyReport = await ReportsAPI.getDailyReport('2026-01-03');
// 首次调用: 从服务器加载并缓存
// 后续调用: 从缓存加载 (30分钟内)

// 2. 强制刷新 (跳过缓存)
const freshReport = await ReportsAPI.getDailyReport('2026-01-03', true);
// 强制从服务器加载并更新缓存
```

### 高级使用

#### 1. 直接使用缓存服务

```typescript
import { reportCache } from '../services/reportCacheService';

// 获取缓存
const cachedData = reportCache.daily.get('2026-01-03');

// 设置缓存
reportCache.daily.set('2026-01-03', reportData);

// 删除缓存
reportCache.daily.remove('2026-01-03');

// 预加载相邻日期
await reportCache.daily.preload('2026-01-03', async (date) => {
    return await ReportsAPI.getDailyReport(date);
});
```

#### 2. 缓存用户设置

```typescript
import { reportCache } from '../services/reportCacheService';

// 保存用户偏好
reportCache.settings.set('theme', 'dark');
reportCache.settings.set('language', 'zh-CN');
reportCache.settings.set('chartType', 'line');

// 读取用户偏好
const theme = reportCache.settings.get<string>('theme');
const language = reportCache.settings.get<string>('language');
```

#### 3. 使用通用缓存管理器

```typescript
import { CacheManager } from '../utils/cacheManager';

// 设置自定义缓存
CacheManager.set('myData', { foo: 'bar' }, {
    ttl: 60 * 60 * 1000, // 1 小时
    version: '1.0.0',
});

// 获取缓存
const data = CacheManager.get('myData', '1.0.0');

// 检查缓存是否存在
if (CacheManager.has('myData')) {
    console.log('缓存存在');
}

// 更新过期时间
CacheManager.touch('myData', 2 * 60 * 60 * 1000); // 延长 2 小时

// 批量操作
CacheManager.setMultiple([
    { key: 'key1', value: 'value1', options: { ttl: 3600000 } },
    { key: 'key2', value: 'value2', options: { ttl: 7200000 } },
]);

const results = CacheManager.getMultiple(['key1', 'key2']);
```

#### 4. 缓存统计和管理

```typescript
import { CacheManager } from '../utils/cacheManager';
import { ReportCacheService } from '../services/reportCacheService';

// 获取缓存统计
const stats = ReportCacheService.getCacheStats();
console.log('缓存统计:', stats);
// 输出: { dailyReports: 5, weeklyReports: 2, monthlyReports: 1, ... }

// 获取详细统计
const detailedStats = CacheManager.getStats();
console.log('详细统计:', detailedStats);
// 输出: { totalItems: 10, totalSize: 52480, expiredItems: 2, ... }

// 清除过期缓存
const clearedCount = CacheManager.clearExpired();
console.log(`清除了 ${clearedCount} 个过期缓存`);

// 清除所有报告缓存
ReportCacheService.clearAllReports();

// 清除指定日期范围的缓存
ReportCacheService.clearDailyReportsInRange('2026-01-01', '2026-01-31');
```

## 🎨 缓存管理界面

项目包含一个可视化的缓存管理组件:

```typescript
import CacheManagerComponent from '../components/CacheManager';

// 在设置页面或调试页面使用
<CacheManagerComponent />
```

功能:
- 📊 显示缓存统计信息
- 🗑️ 清除过期缓存
- 🔄 清除所有报告缓存
- ⚠️ 清除所有缓存

## 🔧 配置和自定义

### 修改缓存过期时间

编辑 `frontend/services/reportCacheService.ts`:

```typescript
private static readonly CACHE_TTL = {
    dailyCurrent: 30 * 60 * 1000,        // 修改为你想要的时间
    dailyHistory: 24 * 60 * 60 * 1000,
    // ...
};
```

### 修改自动清理间隔

编辑 `frontend/utils/cacheManager.ts`:

```typescript
export function initCacheCleanup(): void {
    // 修改清理间隔 (默认 1 小时)
    setInterval(() => {
        CacheManager.clearExpired();
    }, 60 * 60 * 1000); // 修改这里
}
```

## 📊 缓存工作流程

```
用户请求数据
    ↓
检查 forceRefresh?
    ↓ No
检查缓存是否存在?
    ↓ Yes
检查缓存是否过期?
    ↓ No
返回缓存数据 ✅
    
    ↓ (任何 No 路径)
从服务器获取数据
    ↓
转换数据格式
    ↓
保存到缓存
    ↓
返回数据 ✅
```

## 🐛 调试和监控

### 查看缓存日志

打开浏览器控制台,可以看到:
```
[CacheManager] 缓存统计: { 总缓存项: 10, 总大小: "51.25KB", 过期项: 0 }
[API] 从缓存加载日报告: 2026-01-03
[API] 从服务器加载周报告: 2026-01-01
[API] 已缓存周报告: 2026-01-01
```

### 手动检查 LocalStorage

在浏览器控制台:
```javascript
// 查看所有缓存键
Object.keys(localStorage).filter(k => k.startsWith('lifewatch_'))

// 查看特定缓存
JSON.parse(localStorage.getItem('lifewatch_report_daily_2026-01-03'))
```

## ⚠️ 注意事项

1. **存储限制**: LocalStorage 通常限制为 5-10MB,系统会在接近限制时发出警告
2. **隐私模式**: 在浏览器隐私模式下,LocalStorage 可能不可用或在关闭时清除
3. **跨域限制**: LocalStorage 是按域名隔离的,不同域名无法共享缓存
4. **数据安全**: 不要在 LocalStorage 中存储敏感信息(如密码、token)

## 🚀 性能优化建议

1. **预加载**: 使用 `preloadAdjacentDays()` 预加载相邻日期的数据
2. **批量操作**: 使用 `setMultiple()` 和 `getMultiple()` 减少操作次数
3. **合理的 TTL**: 根据数据更新频率设置合适的过期时间
4. **定期清理**: 定期清除不再需要的缓存

## 📝 示例场景

### 场景 1: 用户浏览日报告

```typescript
// 用户打开今天的报告
const todayReport = await ReportsAPI.getDailyReport('2026-01-03');
// 首次加载: 从服务器获取 (耗时 ~500ms)

// 用户切换到其他页面后返回
const todayReport2 = await ReportsAPI.getDailyReport('2026-01-03');
// 从缓存加载: 瞬间返回 (耗时 <10ms) ⚡

// 30 分钟后再次访问
const todayReport3 = await ReportsAPI.getDailyReport('2026-01-03');
// 缓存已过期: 重新从服务器获取
```

### 场景 2: 用户点击"重新计算"

```typescript
// 用户点击重新计算按钮
const freshReport = await ReportsAPI.getDailyReport('2026-01-03', true);
// forceRefresh=true: 跳过缓存,强制从服务器加载
// 新数据会更新缓存
```

### 场景 3: 保存用户偏好

```typescript
// 用户更改主题
reportCache.settings.set('theme', 'dark');

// 下次打开应用
const theme = reportCache.settings.get<string>('theme');
// 返回: 'dark' (即使关闭浏览器后重新打开)
```

## 🎉 总结

LocalStorage 缓存系统已完全集成到项目中,无需额外配置即可使用。系统会:
- ✅ 自动缓存所有报告数据
- ✅ 智能管理缓存过期
- ✅ 自动清理过期数据
- ✅ 提供可视化管理界面

享受更快的应用体验! 🚀
