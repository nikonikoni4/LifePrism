import { Editor } from '@tiptap/react';

export interface MarkdownEditorProps {
  /** Initial Markdown content */
  value?: string;
  /** Callback when content changes */
  onChange?: (markdown: string) => void;
  /** Placeholder text */
  placeholder?: string;
  /** Read-only mode */
  readOnly?: boolean;
  /** Auto focus on mount */
  autoFocus?: boolean;
  /** Container class name */
  className?: string;
  /** Minimum height */
  minHeight?: string;
  /** Maximum height */
  maxHeight?: string;
}

export interface MarkdownEditorRef {
  /** Get current content as Markdown */
  getMarkdown: () => string;
  /** Set content from Markdown */
  setMarkdown: (content: string) => void;
  /** Focus the editor */
  focus: () => void;
  /** Blur the editor */
  blur: () => void;
  /** Get the Tiptap editor instance */
  getEditor: () => Editor | null;
}

export interface SlashCommandItem {
  title: string;
  description: string;
  icon: React.ReactNode;
  command: (editor: Editor) => void;
}

export interface SlashMenuProps {
  editor: Editor;
  items: SlashCommandItem[];
  command: (item: SlashCommandItem) => void;
  clientRect: (() => DOMRect | null) | null;
}

export interface BubbleMenuButtonProps {
  icon: React.ReactNode;
  isActive?: boolean;
  onClick: () => void;
  title?: string;
}
