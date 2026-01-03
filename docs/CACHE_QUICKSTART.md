# LocalStorage 缓存 - 快速开始

## 🚀 5 分钟快速上手

### 1. 报告数据自动缓存 (已启用)

**无需任何修改,缓存已自动工作!**

```typescript
// 在你的组件中
import { ReportsAPI } from './page/reports/api';

// 获取日报告 - 自动使用缓存
const report = await ReportsAPI.getDailyReport('2026-01-03');
// 第一次: 从服务器加载 (~500ms)
// 第二次: 从缓存加载 (<10ms) ⚡

// 强制刷新 - 跳过缓存
const freshReport = await ReportsAPI.getDailyReport('2026-01-03', true);
```

### 2. 保存用户设置

```typescript
import { reportCache } from './services/reportCacheService';

// 保存主题设置
reportCache.settings.set('theme', 'dark');

// 读取主题设置
const theme = reportCache.settings.get<string>('theme');
console.log(theme); // 'dark'

// 保存复杂对象
reportCache.settings.set('preferences', {
    language: 'zh-CN',
    notifications: true,
    chartType: 'line',
});
```

### 3. 使用 React Hook (推荐)

```typescript
import { useUserSettings } from './shared/hooks/useUserSettings';

function MyComponent() {
    const { settings, updateSettings } = useUserSettings();

    return (
        <div>
            <p>当前主题: {settings.theme}</p>
            <button onClick={() => updateSettings({ theme: 'dark' })}>
                切换到暗色主题
            </button>
        </div>
    );
}
```

### 4. 添加缓存管理界面

```typescript
import CacheManagerComponent from './components/CacheManager';

// 在设置页面添加
function SettingsPage() {
    return (
        <div>
            <h1>设置</h1>
            <CacheManagerComponent />
        </div>
    );
}
```

## 📊 查看缓存效果

### 方法 1: 浏览器控制台

打开浏览器开发者工具 (F12),查看 Console:

```
[CacheManager] 缓存统计: { 总缓存项: 5, 总大小: "25.3KB", 过期项: 0 }
[API] 从缓存加载日报告: 2026-01-03 ⚡
```

### 方法 2: Application 标签

1. 打开开发者工具 (F12)
2. 切换到 "Application" 标签
3. 左侧选择 "Local Storage" → 你的域名
4. 查看所有 `lifewatch_` 开头的缓存项

### 方法 3: 使用缓存管理组件

在你的应用中添加 `<CacheManagerComponent />`,可视化查看:
- 📊 缓存统计
- 🗑️ 清除缓存
- 📈 存储空间使用情况

## ✅ 验证缓存是否工作

### 测试步骤:

1. **首次加载**
   ```typescript
   console.time('首次加载');
   const report1 = await ReportsAPI.getDailyReport('2026-01-03');
   console.timeEnd('首次加载');
   // 输出: 首次加载: 523ms
   ```

2. **从缓存加载**
   ```typescript
   console.time('缓存加载');
   const report2 = await ReportsAPI.getDailyReport('2026-01-03');
   console.timeEnd('缓存加载');
   // 输出: 缓存加载: 3ms ⚡⚡⚡
   ```

3. **查看控制台日志**
   ```
   [API] 从服务器加载日报告: 2026-01-03
   [API] 已缓存日报告: 2026-01-03
   [API] 从缓存加载日报告: 2026-01-03 ← 成功!
   ```

## 🎯 常见使用场景

### 场景 1: 保存用户的图表类型偏好

```typescript
// 用户选择图表类型
function ChartTypeSelector() {
    const [chartType, setChartType] = useSetting('chartType');
    
    return (
        <select 
            value={chartType} 
            onChange={(e) => setChartType(e.target.value as any)}
        >
            <option value="line">折线图</option>
            <option value="area">面积图</option>
            <option value="bar">柱状图</option>
        </select>
    );
}
// 下次打开应用,自动恢复用户选择 ✅
```

### 场景 2: 记住用户上次查看的日期

```typescript
// 保存上次查看的日期
reportCache.settings.set('lastViewedDate', '2026-01-03');

// 下次打开应用时恢复
const lastDate = reportCache.settings.get<string>('lastViewedDate') || getTodayDate();
```

### 场景 3: 缓存计算结果

```typescript
import { CacheManager } from './utils/cacheManager';

// 缓存复杂计算结果
function expensiveCalculation(data: any[]) {
    const cacheKey = `calc_${JSON.stringify(data).slice(0, 50)}`;
    
    // 检查缓存
    const cached = CacheManager.get(cacheKey);
    if (cached) return cached;
    
    // 执行计算
    const result = /* 复杂计算 */;
    
    // 缓存结果 (10 分钟)
    CacheManager.set(cacheKey, result, { ttl: 10 * 60 * 1000 });
    
    return result;
}
```

## 🔧 调试技巧

### 1. 清除特定缓存

```typescript
// 清除某天的日报告缓存
reportCache.daily.remove('2026-01-03');

// 清除所有报告缓存
reportCache.clearAll();
```

### 2. 查看缓存信息

```typescript
import { CacheManager } from './utils/cacheManager';

// 获取缓存详情 (不包含数据)
const info = CacheManager.getInfo('report_daily_2026-01-03');
console.log(info);
// { expiry: 1735891234567, version: undefined, createdAt: 1735887634567 }

// 检查是否过期
const isValid = CacheManager.has('report_daily_2026-01-03');
```

### 3. 手动清理

```typescript
// 清理过期缓存
const count = CacheManager.clearExpired();
console.log(`清理了 ${count} 个过期项`);

// 清理所有缓存
CacheManager.clear();
```

## 📝 下一步

- 📖 阅读完整文档: `docs/CACHE_GUIDE.md`
- 🎨 自定义缓存过期时间
- 🔧 集成到更多组件
- 📊 监控缓存性能

## 💡 提示

- ✅ 缓存会自动过期,无需手动管理
- ✅ 应用启动时自动清理过期缓存
- ✅ 强制刷新会更新缓存
- ✅ 关闭浏览器后缓存仍然保留

享受飞快的加载速度! 🚀
