
import React from 'react';
import { PlanDocEditorViewProps } from './types';

export const PlanDocEditorView: React.FC<PlanDocEditorViewProps> = ({ 
    content, 
    onChange, 
    placeholder = "# Start your plan here...",
    className = ""
}) => {
  return (
    <div className={`w-full h-full relative group ${className}`}>
       <textarea
           value={content}
           onChange={(e) => onChange(e.target.value)}
           placeholder={placeholder}
           className="w-full h-full p-8 bg-transparent border-none outline-none resize-none font-mono text-sm text-slate-700 leading-loose placeholder:text-slate-300 focus:bg-white/30 transition-colors"
           spellCheck={false}
       />
    </div>
  );
};
