import React from 'react';

interface HabitLayoutProps {
    children: React.ReactNode;
}

export const HabitLayout: React.FC<HabitLayoutProps> = ({ children }) => {
    return (
        <div className="h-screen w-full flex justify-center bg-slate-50 py-4 px-4 sm:px-6 lg:px-8 overflow-y-auto overflow-x-hidden">
            <div className="text-neutral-900 font-sans min-h-full w-full max-w-[1280px] flex flex-col gap-3 pb-8">
                {children}
            </div>
        </div>
    );
};
