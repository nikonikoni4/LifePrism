import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ModuleDock } from './ModuleDock';
import { ModuleId } from './types';
import { ToastContainer } from '../core/components';

// Import Apps
import { LifeWatchApp } from '../apps/lifewatch/LifeWatchApp';
import { GoalsApp } from '../apps/goals/GoalsApp';
import { HabitsApp } from '../apps/habits/HabitsApp';
import { SettingsApp } from '../apps/settings/SettingsApp';
import { MindSpaceApp } from '../apps/mindspace/MindSpaceApp';
import { AddonsApp } from '../apps/addons/AddonsApp';
import { CustomRecordsApp } from '../apps/custom-records/CustomRecordsApp';

export const AppShell: React.FC = () => {
    // 模块切换状态 — 初始值从 URL 路径推断，避免 LifeWatchApp catch-all 路由重定向
    const [currentModule, setCurrentModule] = useState<ModuleId>(() => {
        const path = window.location.hash.replace(/^#/, '') || '/';
        if (path.startsWith('/goals')) return 'goals';
        if (path.startsWith('/habits')) return 'habits';
        if (path.startsWith('/settings')) return 'settings';
        if (path.startsWith('/mindspace')) return 'mindspace';
        if (path.startsWith('/addons')) return 'addons';
        if (path.startsWith('/custom-records')) return 'custom-records';
        return 'lifewatch';
    });
    const location = useLocation();
    const navigate = useNavigate();

    // Sync URL -> Module
    useEffect(() => {
        const path = location.pathname;
        if (path.startsWith('/goals')) setCurrentModule('goals');
        else if (path.startsWith('/habits')) setCurrentModule('habits');
        else if (path.startsWith('/settings')) setCurrentModule('settings');
        else if (path.startsWith('/mindspace')) setCurrentModule('mindspace');
        else if (path.startsWith('/addons')) setCurrentModule('addons');
        else if (path.startsWith('/custom-records')) setCurrentModule('custom-records');
        else setCurrentModule('lifewatch'); // Default to lifewatch for /, /home, /timeline, etc.
    }, [location.pathname]);

    // Handle Dock Change -> URL
    const handleModuleChange = (moduleId: ModuleId) => {
        setCurrentModule(moduleId);
        switch (moduleId) {
            case 'lifewatch': navigate('/'); break;
            case 'goals': navigate('/goals'); break;
            case 'habits': navigate('/habits'); break;
            case 'settings': navigate('/settings'); break;
            case 'mindspace': navigate('/mindspace'); break;
            case 'addons': navigate('/addons'); break;
            case 'custom-records': navigate('/custom-records'); break;
        }
    };

    return (
        <div className="min-h-screen bg-[#F9FAFB] text-slate-800 font-sans relative">
            {/* 顶部悬浮模块切换 Dock */}
            <ModuleDock
                currentModule={currentModule}
                onModuleChange={handleModuleChange}
            />

            {/* Render Modules */}
            {currentModule === 'lifewatch' && <LifeWatchApp />}
            {currentModule === 'mindspace' && <MindSpaceApp />}
            {currentModule === 'addons' && <AddonsApp />}
            {/* Note: Logic for additional apps (goals, habits, settings) added if supported by ModuleDock's types and config */}

            {/* 暂时 ModuleDock 只支持 lifewatch, mindspace, addons (based on previous App.tsx logic and potential ModuleDock config). 
                If ModuleDock types allow others, we can add them. 
                Assuming ModuleId union includes others or will be extended. 
                Let's double check ModuleDock types or just add them safely. 
            */}

            {/* 
                Existing ModuleDock config in ModuleDock.tsx only listed lifewatch, mindspace, addons.
                The task prompts 1.5 create 6 placeholder apps.
                Wait, does ModuleDock SUPPORT all 6? 
                I should check frontend/shell/types.ts (moved from components/ModuleDock/types.ts).
                If not, I might need to update ModuleDock config/types to include goals, habits, settings.
                
                For now I will render them if currentModule matches.
            */}
            {currentModule === 'goals' && (
                <GoalsApp />
            )}
            {currentModule === 'habits' && (
                <HabitsApp />
            )}
            {currentModule === 'settings' && (
                  <SettingsApp />
              )}
              {currentModule === 'custom-records' && (
                  <CustomRecordsApp />
              )}

            {/* Toast 消息容器 (Global) */}
            <ToastContainer />
        </div>
    );
};
