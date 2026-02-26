import React from 'react';

interface ChainConnectorProps {
  className?: string;
}

export const ChainConnector: React.FC<ChainConnectorProps> = ({ className = '' }) => {
  return (
    <div className={`flex items-center justify-center ${className}`}>
      <div className="flex items-center">
        <div className="w-4 h-0.5 bg-gradient-to-r from-slate-300 to-slate-400" />
        <div className="text-slate-400 text-sm mx-0.5">▶</div>
        <div className="w-4 h-0.5 bg-gradient-to-r from-slate-400 to-slate-300" />
      </div>
    </div>
  );
};

export default ChainConnector;
