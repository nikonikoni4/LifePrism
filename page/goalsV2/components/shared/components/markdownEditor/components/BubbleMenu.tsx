import React, { useEffect, useState, useRef } from 'react';
import { Editor } from '@tiptap/react';
import { BubbleMenuPlugin } from '@tiptap/extension-bubble-menu';
import {
  Bold,
  Italic,
  Underline,
  Strikethrough,
  Code,
  Link,
} from 'lucide-react';
import { BubbleMenuButtonProps } from '../types';

interface BubbleMenuProps {
  editor: Editor;
}

const MenuButton: React.FC<BubbleMenuButtonProps> = ({
  icon,
  isActive,
  onClick,
  title,
}) => (
  <button
    type="button"
    onMouseDown={(e) => {
      e.preventDefault(); // Prevent editor blur
      onClick();
    }}
    title={title}
    className={`
      p-2 rounded transition-colors duration-150
      ${isActive
        ? 'bg-indigo-100 text-indigo-600'
        : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
      }
    `}
  >
    {icon}
  </button>
);

export const BubbleMenuComponent: React.FC<BubbleMenuProps> = ({ editor }) => {
  const menuRef = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });

  useEffect(() => {
    if (!editor || !menuRef.current) return;

    const updateMenu = () => {
      const { state, view } = editor;
      const { from, to } = state.selection;
      const hasSelection = from !== to;
      const isTextSelection = !state.selection.empty;

      if (!hasSelection || !isTextSelection) {
        setIsVisible(false);
        return;
      }

      // Get selection coordinates
      const start = view.coordsAtPos(from);
      const end = view.coordsAtPos(to);

      // Calculate position (center above selection)
      const menuWidth = menuRef.current?.offsetWidth || 200;
      const left = Math.max(10, (start.left + end.left) / 2 - menuWidth / 2);
      const top = start.top - 50;

      setPosition({ top, left });
      setIsVisible(true);
    };

    // Listen to selection changes
    editor.on('selectionUpdate', updateMenu);
    // Don't hide on blur - let selection update handle visibility

    return () => {
      editor.off('selectionUpdate', updateMenu);
    };
  }, [editor]);

  const setLink = () => {
    const previousUrl = editor.getAttributes('link').href;
    const url = window.prompt('Enter URL:', previousUrl);

    if (url === null) {
      return;
    }

    if (url === '') {
      editor.chain().focus().extendMarkRange('link').unsetLink().run();
      return;
    }

    editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run();
  };

  if (!isVisible) {
    return (
      <div
        ref={menuRef}
        style={{ position: 'fixed', visibility: 'hidden', pointerEvents: 'none' }}
        className="flex items-center gap-0.5 p-1 bg-white rounded-lg shadow-lg border border-gray-200"
      >
        <MenuButton icon={<Bold size={16} />} isActive={false} onClick={() => {}} />
      </div>
    );
  }

  return (
    <div
      ref={menuRef}
      style={{
        position: 'fixed',
        top: position.top,
        left: position.left,
        zIndex: 50,
      }}
      className="flex items-center gap-0.5 p-1 bg-white rounded-lg shadow-lg border border-gray-200"
    >
      <MenuButton
        icon={<Bold size={16} />}
        isActive={editor.isActive('bold')}
        onClick={() => editor.chain().focus().toggleBold().run()}
        title="Bold (Ctrl+B)"
      />
      <MenuButton
        icon={<Italic size={16} />}
        isActive={editor.isActive('italic')}
        onClick={() => editor.chain().focus().toggleItalic().run()}
        title="Italic (Ctrl+I)"
      />
      <MenuButton
        icon={<Underline size={16} />}
        isActive={editor.isActive('underline')}
        onClick={() => editor.chain().focus().toggleUnderline().run()}
        title="Underline (Ctrl+U)"
      />
      <MenuButton
        icon={<Strikethrough size={16} />}
        isActive={editor.isActive('strike')}
        onClick={() => editor.chain().focus().toggleStrike().run()}
        title="Strikethrough"
      />
      <div className="w-px h-5 bg-gray-200 mx-1" />
      <MenuButton
        icon={<Code size={16} />}
        isActive={editor.isActive('code')}
        onClick={() => editor.chain().focus().toggleCode().run()}
        title="Inline Code"
      />
      <MenuButton
        icon={<Link size={16} />}
        isActive={editor.isActive('link')}
        onClick={setLink}
        title="Link"
      />
    </div>
  );
};
