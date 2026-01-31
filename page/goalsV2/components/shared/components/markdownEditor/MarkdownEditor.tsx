import React, {
  forwardRef,
  useImperativeHandle,
  useEffect,
  useState,
} from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Placeholder from '@tiptap/extension-placeholder';
import UnderlineExtension from '@tiptap/extension-underline';
import TaskList from '@tiptap/extension-task-list';
import TaskItem from '@tiptap/extension-task-item';
import { Table } from '@tiptap/extension-table';
import TableRow from '@tiptap/extension-table-row';
import TableCell from '@tiptap/extension-table-cell';
import TableHeader from '@tiptap/extension-table-header';
import LinkExtension from '@tiptap/extension-link';
import ImageExtension from '@tiptap/extension-image';

import { MarkdownEditorProps, MarkdownEditorRef, SlashCommandItem } from './types';
import { editorToMarkdown, markdownToHtml } from './utils';
import { SlashCommand, slashCommandItems, SlashCommandPluginKey } from './extensions/SlashCommand';
import { BubbleMenuComponent } from './components/BubbleMenu';
import { SlashMenu } from './components/SlashMenu';

export const MarkdownEditor = forwardRef<MarkdownEditorRef, MarkdownEditorProps>(
  (
    {
      value = '',
      onChange,
      placeholder = 'Type "/" for commands...',
      readOnly = false,
      autoFocus = false,
      className = '',
      minHeight = '200px',
      maxHeight,
    },
    ref
  ) => {
    const [slashMenuProps, setSlashMenuProps] = useState<{
      items: SlashCommandItem[];
      command: (item: SlashCommandItem) => void;
      clientRect: (() => DOMRect | null) | null;
    } | null>(null);

    const editor = useEditor({
      extensions: [
        StarterKit.configure({
          heading: {
            levels: [1, 2, 3],
          },
        }),
        Placeholder.configure({
          placeholder,
          emptyEditorClass: 'is-editor-empty',
        }),
        UnderlineExtension,
        TaskList,
        TaskItem.configure({
          nested: true,
        }),
        Table.configure({
          resizable: true,
        }),
        TableRow,
        TableCell,
        TableHeader,
        LinkExtension.configure({
          openOnClick: false,
          HTMLAttributes: {
            class: 'text-indigo-600 underline cursor-pointer hover:text-indigo-800',
          },
        }),
        ImageExtension.configure({
          HTMLAttributes: {
            class: 'max-w-full h-auto rounded',
          },
        }),
        SlashCommand.configure({
          suggestion: {
            char: '/',
            pluginKey: SlashCommandPluginKey,
            items: ({ query }) => {
              return slashCommandItems.filter((item) =>
                item.title.toLowerCase().includes(query.toLowerCase())
              );
            },
            command: ({ editor, range, props }) => {
              // Delete the slash command text first
              editor.chain().focus().deleteRange(range).run();
              // Then execute the command
              (props as SlashCommandItem).command(editor as any);
            },
            render: () => {
              return {
                onStart: (props) => {
                  setSlashMenuProps({
                    items: props.items as SlashCommandItem[],
                    command: (item) => {
                      props.command(item);
                    },
                    clientRect: props.clientRect,
                  });
                },
                onUpdate: (props) => {
                  setSlashMenuProps({
                    items: props.items as SlashCommandItem[],
                    command: (item) => {
                      props.command(item);
                    },
                    clientRect: props.clientRect,
                  });
                },
                onKeyDown: (props) => {
                  if (props.event.key === 'Escape') {
                    setSlashMenuProps(null);
                    return true;
                  }
                  return false;
                },
                onExit: () => {
                  setSlashMenuProps(null);
                },
              };
            },
          },
        }),
      ],
      content: value ? markdownToHtml(value) : '',
      editable: !readOnly,
      autofocus: autoFocus,
      onUpdate: ({ editor }) => {
        if (onChange) {
          const markdown = editorToMarkdown(editor);
          onChange(markdown);
        }
      },
      editorProps: {
        attributes: {
          class: 'prose prose-sm sm:prose max-w-none focus:outline-none text-left',
        },
      },
    });

    // Expose methods via ref
    useImperativeHandle(ref, () => ({
      getMarkdown: () => {
        if (!editor) return '';
        return editorToMarkdown(editor);
      },
      setMarkdown: (content: string) => {
        if (!editor) return;
        editor.commands.setContent(markdownToHtml(content));
      },
      focus: () => {
        editor?.commands.focus();
      },
      blur: () => {
        editor?.commands.blur();
      },
      getEditor: () => editor,
    }));

    // Update content when value prop changes
    useEffect(() => {
      if (editor && value !== undefined) {
        const currentMarkdown = editorToMarkdown(editor);
        if (currentMarkdown !== value) {
          editor.commands.setContent(markdownToHtml(value));
        }
      }
    }, [value, editor]);

    // Update editable state
    useEffect(() => {
      if (editor) {
        editor.setEditable(!readOnly);
      }
    }, [readOnly, editor]);

    if (!editor) {
      return null;
    }

    return (
      <div
        className={`markdown-editor ${className}`}
        style={{
          minHeight,
          maxHeight,
          overflowY: maxHeight ? 'auto' : undefined,
        }}
      >
        <style>{`
          .markdown-editor .ProseMirror {
            min-height: ${minHeight};
            padding: 1rem;
            outline: none;
          }

          .markdown-editor .ProseMirror.is-editor-empty:first-child::before {
            content: attr(data-placeholder);
            float: left;
            color: #9ca3af;
            pointer-events: none;
            height: 0;
          }

          .markdown-editor .ProseMirror h1,
          .markdown-editor .ProseMirror h2,
          .markdown-editor .ProseMirror h3 {
            color: #000;
            font-weight: 600;
            line-height: 1.3;
            margin-top: 1.5em;
            margin-bottom: 0.5em;
          }

          .markdown-editor .ProseMirror h1 {
            font-size: 2em;
          }

          .markdown-editor .ProseMirror h2 {
            font-size: 1.5em;
          }

          .markdown-editor .ProseMirror h3 {
            font-size: 1.25em;
          }

          .markdown-editor .ProseMirror p {
            margin: 0.75em 0;
          }

          .markdown-editor .ProseMirror ul,
          .markdown-editor .ProseMirror ol {
            padding-left: 1.5em;
            margin: 0.5em 0;
          }

          .markdown-editor .ProseMirror ul:not([data-type="taskList"]) {
            list-style-type: disc;
          }

          .markdown-editor .ProseMirror ol {
            list-style-type: decimal;
          }

          .markdown-editor .ProseMirror li {
            margin: 0.25em 0;
          }

          .markdown-editor .ProseMirror ul[data-type="taskList"] {
            list-style: none;
            padding-left: 0;
          }

          .markdown-editor .ProseMirror ul[data-type="taskList"] li {
            display: flex;
            align-items: flex-start;
            gap: 0.5em;
          }

          .markdown-editor .ProseMirror ul[data-type="taskList"] li > label {
            flex-shrink: 0;
            display: flex;
            align-items: center;
            height: 1.5em;
          }

          .markdown-editor .ProseMirror ul[data-type="taskList"] li > div {
            flex: 1;
          }

          .markdown-editor .ProseMirror ul[data-type="taskList"] li > div p {
            margin: 0;
          }

          .markdown-editor .ProseMirror ul[data-type="taskList"] input[type="checkbox"] {
            width: 1em;
            height: 1em;
            cursor: pointer;
            accent-color: #6366f1;
            margin-top: 0.15em;
          }

          .markdown-editor .ProseMirror blockquote {
            border-left: 3px solid #e5e7eb;
            padding-left: 1em;
            margin: 1em 0;
            color: #6b7280;
          }

          .markdown-editor .ProseMirror pre {
            background: #1f2937;
            color: #f3f4f6;
            padding: 1em;
            border-radius: 0.5em;
            overflow-x: auto;
            margin: 1em 0;
          }

          .markdown-editor .ProseMirror code {
            background: #f3f4f6;
            padding: 0.2em 0.4em;
            border-radius: 0.25em;
            font-size: 0.9em;
          }

          .markdown-editor .ProseMirror pre code {
            background: none;
            padding: 0;
          }

          .markdown-editor .ProseMirror hr {
            border: none;
            border-top: 2px solid #e5e7eb;
            margin: 1.5em 0;
          }

          .markdown-editor .ProseMirror table {
            border-collapse: collapse;
            width: 100%;
            margin: 1em 0;
          }

          .markdown-editor .ProseMirror th,
          .markdown-editor .ProseMirror td {
            border: 1px solid #e5e7eb;
            padding: 0.5em 1em;
            text-align: left;
          }

          .markdown-editor .ProseMirror th {
            background: #f9fafb;
            font-weight: 600;
          }

          .markdown-editor .ProseMirror img {
            max-width: 100%;
            height: auto;
            border-radius: 0.5em;
          }
        `}</style>

        <BubbleMenuComponent editor={editor} />
        <EditorContent editor={editor} />
        {slashMenuProps && (
          <SlashMenu
            items={slashMenuProps.items}
            command={slashMenuProps.command}
            clientRect={slashMenuProps.clientRect}
          />
        )}
      </div>
    );
  }
);

MarkdownEditor.displayName = 'MarkdownEditor';

export default MarkdownEditor;
