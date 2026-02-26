import React from 'react';

interface SinglePaneLayoutProps {
  children: React.ReactNode;
}

export const SinglePaneLayout: React.FC<SinglePaneLayoutProps> = ({ children }) => {
  return (
    <div className="flex h-full w-full overflow-hidden justify-center">
      <div className="w-full max-w-5xl h-full flex flex-col bg-white/90 backdrop-blur rounded-[24px] shadow-soft-lg border border-white/60 overflow-hidden transition-all duration-300 hover:shadow-soft-hover">
        {children}
      </div>
    </div>
  );
};