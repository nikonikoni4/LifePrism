import React from 'react';

interface HabitLayoutProps {
    children: React.ReactNode;
}

export const HabitLayout: React.FC<HabitLayoutProps> = ({ children }) => {
    return (
        <div className="h-screen w-full flex justify-center py-4 px-4 sm:px-6 lg:px-8 overflow-hidden">
            <div className="text-neutral-900 font-sans h-full w-full max-w-[1280px] overflow-hidden flex flex-col gap-3">
                {children}
            </div>
        </div>
    );
};
