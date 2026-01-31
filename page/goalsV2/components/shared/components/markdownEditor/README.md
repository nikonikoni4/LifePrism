# MarkdownEditor

基于 Tiptap 的 Markdown 编辑器组件，支持斜杠命令、气泡菜单和丰富的格式化功能。

## 安装依赖

```bash
npm install @tiptap/react @tiptap/starter-kit @tiptap/extension-placeholder \
  @tiptap/extension-underline @tiptap/extension-task-list @tiptap/extension-task-item \
  @tiptap/extension-table @tiptap/extension-table-row @tiptap/extension-table-cell \
  @tiptap/extension-table-header @tiptap/extension-link @tiptap/extension-image \
  @tiptap/suggestion @tiptap/pm lucide-react
```

## 基本用法

```tsx
import { MarkdownEditor } from './markdownEditor';

function App() {
  const [content, setContent] = useState('');

  return (
    <MarkdownEditor
      value={content}
      onChange={setContent}
      placeholder="输入 / 打开命令菜单..."
    />
  );
}
```

## Props

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `value` | `string` | `''` | 初始 Markdown 内容 |
| `onChange` | `(markdown: string) => void` | - | 内容变化回调 |
| `placeholder` | `string` | `'Type "/" for commands...'` | 占位符文本 |
| `readOnly` | `boolean` | `false` | 只读模式 |
| `autoFocus` | `boolean` | `false` | 自动聚焦 |
| `className` | `string` | `''` | 容器类名 |
| `minHeight` | `string` | `'200px'` | 最小高度 |
| `maxHeight` | `string` | - | 最大高度（设置后启用滚动） |

## Ref 方法

通过 `ref` 可以访问编辑器实例方法：

```tsx
import { useRef } from 'react';
import { MarkdownEditor, MarkdownEditorRef } from './markdownEditor';

function App() {
  const editorRef = useRef<MarkdownEditorRef>(null);

  const handleGetContent = () => {
    const markdown = editorRef.current?.getMarkdown();
    console.log(markdown);
  };

  const handleSetContent = () => {
    editorRef.current?.setMarkdown('# Hello World');
  };

  return (
    <>
      <MarkdownEditor ref={editorRef} />
      <button onClick={handleGetContent}>获取内容</button>
      <button onClick={handleSetContent}>设置内容</button>
    </>
  );
}
```

### 可用方法

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `getMarkdown()` | `string` | 获取当前内容的 Markdown 格式 |
| `setMarkdown(content)` | `void` | 设置 Markdown 内容 |
| `focus()` | `void` | 聚焦编辑器 |
| `blur()` | `void` | 取消聚焦 |
| `getEditor()` | `Editor \| null` | 获取 Tiptap Editor 实例 |

## 斜杠命令

输入 `/` 可打开命令菜单，支持以下命令：

| 命令 | 说明 |
|------|------|
| Heading 1 | 一级标题 |
| Heading 2 | 二级标题 |
| Heading 3 | 三级标题 |
| Bullet List | 无序列表 |
| Numbered List | 有序列表 |
| Task List | 任务列表（带勾选框） |
| Quote | 引用块 |
| Code Block | 代码块 |
| Divider | 分割线 |
| Table | 插入表格（3x3） |
| Image | 插入图片（URL） |

## 气泡菜单

选中文本后会显示气泡菜单，支持以下格式化操作：

- **粗体** (Bold)
- *斜体* (Italic)
- <u>下划线</u> (Underline)
- ~~删除线~~ (Strike)
- `代码` (Code)
- [链接](Link)

## 示例

### 只读模式

```tsx
<MarkdownEditor
  value="# 只读内容\n\n这是只读模式的编辑器。"
  readOnly
/>
```

### 限制高度

```tsx
<MarkdownEditor
  value={content}
  onChange={setContent}
  minHeight="100px"
  maxHeight="400px"
/>
```

### 自定义样式

```tsx
<MarkdownEditor
  value={content}
  onChange={setContent}
  className="border rounded-lg shadow-sm"
/>
```

## 导出

```tsx
// 组件
export { MarkdownEditor } from './markdownEditor';

// 类型
export type { MarkdownEditorProps, MarkdownEditorRef, SlashCommandItem } from './types';

// 工具函数
export { editorToMarkdown, markdownToHtml } from './utils';

// 子组件（高级用法）
export { BubbleMenuComponent } from './components/BubbleMenu';
export { SlashMenu } from './components/SlashMenu';
export { SlashCommand, slashCommandItems } from './extensions/SlashCommand';
```
