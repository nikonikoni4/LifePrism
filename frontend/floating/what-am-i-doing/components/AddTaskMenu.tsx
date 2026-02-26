import React, { useState, useRef, useEffect } from 'react';

interface AddTaskMenuProps {
    onCreateNew: () => void;
    onSelectExisting: () => void;
}

export function AddTaskMenu({ onCreateNew, onSelectExisting }: AddTaskMenuProps) {
    const [open, setOpen] = useState(false);
    const menuRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!open) return;
        const handleClick = (e: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
                setOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClick);
        return () => document.removeEventListener('mousedown', handleClick);
    }, [open]);

    return (
        <div className="relative" ref={menuRef}>
            <button
                onClick={() => setOpen(!open)}
                className="w-full flex items-center justify-center gap-1 py-1.5 text-white/40 hover:text-white/70 hover:bg-white/5 rounded transition-colors text-sm"
            >
                <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <line x1="8" y1="3" x2="8" y2="13" />
                    <line x1="3" y1="8" x2="13" y2="8" />
                </svg>
                Add
            </button>
            {open && (
                <div className="absolute bottom-full left-0 right-0 mb-1 bg-[#2a2a2a] border border-white/10 rounded-md shadow-xl z-50 py-1">
                    <button
                        onClick={() => { setOpen(false); onCreateNew(); }}
                        className="w-full text-left px-3 py-1.5 text-sm text-white/70 hover:bg-white/10 hover:text-white"
                    >
                        New task
                    </button>
                    <button
                        onClick={() => { setOpen(false); onSelectExisting(); }}
                        className="w-full text-left px-3 py-1.5 text-sm text-white/70 hover:bg-white/10 hover:text-white"
                    >
                        Select existing
                    </button>
                </div>
            )}
        </div>
    );
}
