import React from 'react';

export const Background: React.FC = () => {
    return (
        <div className="fixed inset-0 pointer-events-none z-[-1]">
             <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] rounded-full bg-indigo-200/20 blur-[100px]" />
             <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] rounded-full bg-rose-200/20 blur-[100px]" />
        </div>
    );
};