import React from 'react';

interface HabitLayoutProps {
    children: React.ReactNode;
}

export const HabitLayout: React.FC<HabitLayoutProps> = ({ children }) => {
    return (
        <div className="bg-slate-50 text-neutral-900 font-sans h-full w-full overflow-hidden flex flex-col p-4 lg:p-6 gap-3 rounded-[32px] shadow-sm border border-neutral-100">
            {children}
        </div>
    );
};
