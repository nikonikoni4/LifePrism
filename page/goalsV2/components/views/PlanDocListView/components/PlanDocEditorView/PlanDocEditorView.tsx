
import React from 'react';
import { PlanDocEditorViewProps } from '../../../../types';
import { MarkdownEditor } from '@my-ui-kit/core';

export const PlanDocEditorView: React.FC<PlanDocEditorViewProps> = ({
    content,
    onChange,
    placeholder = "Type '/' for commands...",
    className = ""
}) => {
  return (
    <div className={`w-full h-full relative ${className}`}>
       <MarkdownEditor
           value={content}
           onChange={onChange}
           placeholder={placeholder}
           className="w-full h-full"
           minHeight="100%"
       />
    </div>
  );
};
