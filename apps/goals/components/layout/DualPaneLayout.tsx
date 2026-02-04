import React from 'react';

interface DualPaneLayoutProps {
  left: React.ReactNode;
  right: React.ReactNode;
}

export const DualPaneLayout: React.FC<DualPaneLayoutProps> = ({ left, right }) => {
  return (
    <div className="flex h-full w-full gap-5">
      {/* Left Panel - Soft UI Card */}
      <div className="w-[45%] h-full flex flex-col overflow-hidden bg-white/80 backdrop-blur rounded-[20px] shadow-soft-lg border border-white/60 transition-all duration-300 hover:shadow-soft-hover hover:border-aurora-primary/20">
        <div className="h-full overflow-hidden flex flex-col">
            {left}
        </div>
      </div>
      
      {/* Right Panel - Soft UI Card */}
      <div className="flex-1 h-full flex flex-col overflow-hidden bg-white/80 backdrop-blur rounded-[20px] shadow-soft-lg border border-white/60 transition-all duration-300 hover:shadow-soft-hover hover:border-aurora-primary/20">
        <div className="h-full overflow-hidden flex flex-col">
            {right}
        </div>
      </div>
    </div>
  );
};