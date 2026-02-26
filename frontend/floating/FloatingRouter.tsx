import React from 'react';
import { useLocation } from 'react-router-dom';
import { WhatAmIDoingFloat } from './what-am-i-doing/WhatAmIDoingFloat';

export const FloatingRouter: React.FC = () => {
    const location = useLocation();

    // 从 /floating/xxx 中提取 windowId
    const windowId = location.pathname.replace('/floating/', '');

    switch (windowId) {
        case 'what-am-i-doing':
            return <WhatAmIDoingFloat />;
        default:
            return (
                <div className="h-screen flex items-center justify-center bg-slate-900 text-white">
                    <p className="text-sm text-slate-400">未知的浮窗: {windowId}</p>
                </div>
            );
    }
};
