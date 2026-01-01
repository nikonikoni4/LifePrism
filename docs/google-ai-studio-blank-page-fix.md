# Google AI Studio 项目空白页面问题排查指南

## 问题描述

从 Google AI Studio 下载的前端项目在本地运行时显示空白页面，浏览器控制台没有明显错误信息。

## 根本原因

### 1. **Import Maps 与 Vite 的模块解析冲突**

Google AI Studio 导出的项目使用了 **Import Maps** 来从 CDN 加载依赖：

```html
<script type="importmap">
{
  "imports": {
    "react": "https://aistudiocdn.com/react@^19.2.0",
    "react-dom/": "https://aistudiocdn.com/react-dom@^19.2.0/",
    "lucide-react": "https://aistudiocdn.com/lucide-react@^0.555.0",
    ...
  }
}
</script>
```

**问题所在：**
- Import Maps 告诉浏览器从 `aistudiocdn.com` 加载 React 等依赖
- Vite 开发服务器期望从本地 `node_modules` 加载这些依赖
- 两者发生冲突，导致模块加载失败，但不一定会显示明显的错误

### 2. **缺少入口脚本标签**

原始 `index.html` 缺少加载应用入口的脚本标签：

```html
<body>
  <div id="root"></div>
  <!-- ❌ 缺少这行 -->
  <!-- <script type="module" src="/index.tsx"></script> -->
</body>
```

没有这个标签，Vite 无法知道应该加载哪个文件作为应用入口。

## 环境差异对比

| 特性 | Google AI Studio | 本地 Vite 开发环境 |
|------|------------------|-------------------|
| **依赖加载** | CDN（Import Maps） | node_modules（打包工具） |
| **模块系统** | 浏览器原生 ES Modules | Vite 编译 + HMR |
| **入口文件** | 自动处理 | 需要显式声明 |
| **构建流程** | 无需构建 | Vite 开发服务器 |
| **热重载** | 不支持 | 支持（HMR） |

## 解决方案

### 步骤 1：注释掉 Import Maps

在 `index.html` 中找到 `<script type="importmap">` 块并注释掉：

```html
<!-- 
NOTE: Import Maps 与 Vite 冲突，已注释
<script type="importmap">
{
  "imports": {
    ...
  }
}
</script>
-->
```

### 步骤 2：添加入口脚本标签

在 `</body>` 之前添加：

```html
<body class="bg-[#F3F4F6] text-slate-800 antialiased">
  <div id="root"></div>
  <script type="module" src="/index.tsx"></script>
</body>
```

### 步骤 3：确保依赖已安装

```bash
npm install
```

### 步骤 4：启动开发服务器

```bash
npm run dev
```

### 步骤 5：刷新浏览器

访问 `http://localhost:3000` 并强制刷新（Ctrl+F5 或 Cmd+Shift+R）

## 技术原理深入解析

### Import Maps 的工作原理

Import Maps 是现代浏览器的一个特性，允许你控制模块的导入路径：

```javascript
// 代码中这样写
import React from 'react';

// Import Maps 将其映射为
import React from 'https://aistudiocdn.com/react@^19.2.0';
```

### Vite 的模块解析机制

Vite 使用自己的模块解析系统：

1. **开发模式**：拦截浏览器的模块请求，从 `node_modules` 提供依赖
2. **预构建**：将依赖预打包为 ESM 格式
3. **HMR**：提供热模块替换功能

当 Import Maps 存在时：
- 浏览器尝试从 CDN 加载模块
- Vite 的拦截机制失效
- 导致模块加载混乱

### 为什么控制台可能没有错误？

1. **静默失败**：模块加载失败但没有抛出异常
2. **CORS 问题**：CDN 资源可能被浏览器静默阻止
3. **React 未渲染**：如果 React 根本没加载，就不会有 render 错误

## 诊断清单

如果遇到空白页面问题，按顺序检查：

- [ ] **检查控制台错误**：打开浏览器开发者工具（F12）
- [ ] **查看网络请求**：确认哪些资源加载失败
- [ ] **检查 Import Maps**：查看 `index.html` 是否有 `<script type="importmap">`
- [ ] **验证入口脚本**：确认 `<script type="module" src="/index.tsx">` 存在
- [ ] **确认开发服务器**：确保使用 `npm run dev` 而非直接打开 HTML
- [ ] **检查依赖安装**：运行 `npm install` 确保所有依赖已安装
- [ ] **清除缓存**：强制刷新浏览器（Ctrl+Shift+R）

## 常见变体问题

### 问题变体 1：只有部分内容显示

**原因**：部分模块从 CDN 加载成功，部分失败

**解决**：完全移除 Import Maps，让 Vite 处理所有依赖

### 问题变体 2：生产构建后仍空白

**原因**：`index.html` 中缺少构建后的脚本引用

**解决**：确保运行 `npm run build` 后，Vite 会自动注入正确的脚本标签

### 问题变体 3：报 "React is not defined" 错误

**原因**：React 从 CDN 加载失败，但代码尝试使用它

**解决**：按上述步骤修复 Import Maps 问题

## 最佳实践

### 从 Google AI Studio 迁移项目时

1. **立即修复 index.html**：第一时间按上述方案修复
2. **检查 package.json**：确保所有依赖都已声明
3. **验证 vite.config.ts**：确认配置正确
4. **测试开发服务器**：确保 `npm run dev` 能正常工作

### 避免类似问题

1. **优先使用本地依赖**：在生产项目中避免 CDN 依赖
2. **使用标准构建工具**：Vite、Webpack、Parcel 等
3. **版本锁定**：使用 `package-lock.json` 锁定依赖版本
4. **环境分离**：开发环境和生产环境使用不同配置

## 参考资源

- [Import Maps 规范](https://github.com/WICG/import-maps)
- [Vite 官方文档](https://vitejs.dev/)
- [Vite 依赖预构建](https://vitejs.dev/guide/dep-pre-bundling.html)

## 总结

Google AI Studio 项目空白页的核心原因是 **Import Maps 与 Vite 的模块解析机制冲突**。解决方法是注释掉 Import Maps，添加入口脚本标签，让 Vite 统一处理所有模块加载。

记住这个原则：**在本地开发环境中，让构建工具（Vite）完全控制模块加载，不要混用 CDN 和 node_modules。**
