import React from 'react';

interface HabitLayoutProps {
    children: React.ReactNode;
}

export const HabitLayout: React.FC<HabitLayoutProps> = ({ children }) => {
    return (
        <div className="h-screen w-full flex justify-center bg-[radial-gradient(1200px_380px_at_8%_-10%,rgba(16,185,129,0.08),transparent_60%),radial-gradient(900px_320px_at_100%_0%,rgba(14,165,233,0.08),transparent_55%),linear-gradient(180deg,#F8FAFC_0%,#EEF2F7_100%)] py-4 px-4 sm:px-6 lg:px-8 overflow-y-auto overflow-x-hidden">
            <div className="text-neutral-900 font-sans min-h-full w-full max-w-[1280px] flex flex-col gap-3 pb-8">
                {children}
            </div>
        </div>
    );
};
