import { Extension } from '@tiptap/core';
import { Editor } from '@tiptap/react';
import Suggestion, { SuggestionOptions } from '@tiptap/suggestion';
import { PluginKey } from '@tiptap/pm/state';
import { SlashCommandItem } from '../types';
import {
  Heading1,
  Heading2,
  Heading3,
  List,
  ListOrdered,
  CheckSquare,
  Quote,
  Code,
  Minus,
  Table,
  Image,
} from 'lucide-react';
import React from 'react';

export const slashCommandItems: SlashCommandItem[] = [
  {
    title: 'Heading 1',
    description: 'Large section heading',
    icon: React.createElement(Heading1, { size: 18 }),
    command: (editor: Editor) => {
      editor.chain().focus().toggleHeading({ level: 1 }).run();
    },
  },
  {
    title: 'Heading 2',
    description: 'Medium section heading',
    icon: React.createElement(Heading2, { size: 18 }),
    command: (editor: Editor) => {
      editor.chain().focus().toggleHeading({ level: 2 }).run();
    },
  },
  {
    title: 'Heading 3',
    description: 'Small section heading',
    icon: React.createElement(Heading3, { size: 18 }),
    command: (editor: Editor) => {
      editor.chain().focus().toggleHeading({ level: 3 }).run();
    },
  },
  {
    title: 'Bullet List',
    description: 'Create a simple bullet list',
    icon: React.createElement(List, { size: 18 }),
    command: (editor: Editor) => {
      editor.chain().focus().toggleBulletList().run();
    },
  },
  {
    title: 'Numbered List',
    description: 'Create a numbered list',
    icon: React.createElement(ListOrdered, { size: 18 }),
    command: (editor: Editor) => {
      editor.chain().focus().toggleOrderedList().run();
    },
  },
  {
    title: 'Task List',
    description: 'Create a todo list with checkboxes',
    icon: React.createElement(CheckSquare, { size: 18 }),
    command: (editor: Editor) => {
      editor.chain().focus().toggleTaskList().run();
    },
  },
  {
    title: 'Quote',
    description: 'Create a blockquote',
    icon: React.createElement(Quote, { size: 18 }),
    command: (editor: Editor) => {
      editor.chain().focus().toggleBlockquote().run();
    },
  },
  {
    title: 'Code Block',
    description: 'Create a code block',
    icon: React.createElement(Code, { size: 18 }),
    command: (editor: Editor) => {
      editor.chain().focus().toggleCodeBlock().run();
    },
  },
  {
    title: 'Divider',
    description: 'Insert a horizontal divider',
    icon: React.createElement(Minus, { size: 18 }),
    command: (editor: Editor) => {
      editor.chain().focus().setHorizontalRule().run();
    },
  },
  {
    title: 'Table',
    description: 'Insert a table',
    icon: React.createElement(Table, { size: 18 }),
    command: (editor: Editor) => {
      editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run();
    },
  },
  {
    title: 'Image',
    description: 'Insert an image from URL',
    icon: React.createElement(Image, { size: 18 }),
    command: (editor: Editor) => {
      const url = window.prompt('Enter image URL:');
      if (url) {
        editor.chain().focus().setImage({ src: url }).run();
      }
    },
  },
];

export const SlashCommandPluginKey = new PluginKey('slashCommand');

export interface SlashCommandOptions {
  suggestion: Omit<SuggestionOptions<SlashCommandItem>, 'editor'>;
}

export const SlashCommand = Extension.create<SlashCommandOptions>({
  name: 'slashCommand',

  addOptions() {
    return {
      suggestion: {
        char: '/',
        pluginKey: SlashCommandPluginKey,
        command: ({ editor, range, props }) => {
          editor.chain().focus().deleteRange(range).run();
          props.command(editor as Editor);
        },
        items: ({ query }) => {
          return slashCommandItems.filter((item) =>
            item.title.toLowerCase().includes(query.toLowerCase())
          );
        },
        // render must be provided by the consumer
      },
    };
  },

  addProseMirrorPlugins() {
    return [
      Suggestion({
        editor: this.editor,
        ...this.options.suggestion,
      }),
    ];
  },
});
