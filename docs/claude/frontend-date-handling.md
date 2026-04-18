# 前端时间处理规范

## 规则

**Date → 日期字符串**，必须使用 `frontend/core/utils/dateUtils.ts` 中的 `toLocalDateString`：

```typescript
import { toLocalDateString } from '@core/utils/dateUtils';

// ✅ 正确
toLocalDateString(someDate); // "2026-03-03"

// ❌ 禁止：toISOString() 返回 UTC，UTC+8 午夜会导致日期减一天
someDate.toISOString().split('T')[0];

// ❌ 禁止：内联重复实现（违反 SSOT）
`${date.getFullYear()}-${...}-${...}`;
```

**后端返回的 `YYYY-MM-DD` 字符串直接使用，不要转 `Date` 再格式化**：

```typescript
// ✅ 直接用
challenge.startDate;

// ❌ 多余且引入时区风险
toLocalDateString(new Date(challenge.startDate));
```

**不适用**：`toLocaleString()` 纯展示调用、`<input type="date/time">` 原生值、后端 Python 代码。

## 暂停机制

遇到以下情况**必须暂停，与用户讨论后再编码**：

- 不确定此场景是否适合用 `toLocalDateString`
- 需要跨时区比较或传递给要求 UTC 的外部 API
- 需要新增其他日期格式化函数
- 后端返回 ISO 8601 带时区字符串，不确定前端应如何处理
