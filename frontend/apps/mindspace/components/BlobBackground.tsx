
import React from 'react';

const BlobBackground: React.FC = () => {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none -z-10 bg-white">
      {/* Top Right - Large Blob */}
      <div 
        className="absolute -top-[10%] -right-[10%] w-[50vw] h-[50vw] rounded-full mix-blend-multiply filter blur-3xl animate-float bg-rose-100 opacity-70" 
      />
      
      {/* Bottom Left - Large Blob */}
      <div 
        className="absolute -bottom-[10%] -left-[10%] w-[50vw] h-[50vw] rounded-full mix-blend-multiply filter blur-3xl animate-float bg-blue-100 opacity-70" 
        style={{ animationDelay: '2s' }} 
      />
      
      {/* Center Right Accent */}
      <div 
        className="absolute top-[30%] right-[10%] w-[20vw] h-[20vw] rounded-full mix-blend-multiply filter blur-2xl animate-float bg-purple-100 opacity-50" 
        style={{ animationDelay: '4s' }} 
      />
    </div>
  );
};

export default BlobBackground;
