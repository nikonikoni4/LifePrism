# Frontend Core Rules

## Electron 原生对话框规则

### 禁止使用原生浏览器对话框

**规则**: 在 Electron 环境中，禁止使用 `window.alert()`、`window.confirm()`、`window.prompt()` 等原生浏览器对话框。

**原因**: 在 Windows 打包环境下，这些原生对话框会导致 BrowserWindow 失去焦点。关闭后焦点无法正确恢复，造成输入框无法输入的问题。这是 Electron 的已知 Bug (#20400)。

**替代方案**: 使用 Electron 的 `dialog` 模块：

```javascript
const { dialog } = require('electron').remote;
```

### confirm 替换模板

```javascript
// 改前（禁止使用）
if (!confirm('确定要删除吗？')) return;

// 改后
const { dialog } = require('electron').remote;
if (dialog.showMessageBoxSync({
  type: 'question',
  buttons: ['取消', '确定'],
  defaultId: 0,
  cancelId: 0,
  title: '确认',
  message: '确定要删除吗？'
}) !== 1) return;
```

### alert 替换模板

```javascript
// 改前（禁止使用）
alert('操作成功');

// 改后（优先使用项目内部的 Toast 提示）
import { toast } from 'xxx'; // 根据项目实际情况
toast.success('操作成功');

// 或使用 Electron dialog
const { dialog } = require('electron').remote;
dialog.showMessageBoxSync({
  type: 'info',
  buttons: ['确定'],
  title: '提示',
  message: '操作成功'
});
```

### prompt 替换模板

```javascript
// 改前（禁止使用）
const name = window.prompt('请输入名称:');

// 改后：使用自定义输入对话框组件
// 或在 Electron 主进程创建原生输入对话框
```

### 触发场景

1. 新增 `confirm()`、`alert()`、`prompt()` 调用时
2. Code Review 时发现使用原生对话框时
3. 重构相关删除/确认逻辑时

### 例外情况

- `my-ui-kit` 目录下的独立测试项目不受此限制
- Electron 环境之外的纯 Web 测试代码不受此限制