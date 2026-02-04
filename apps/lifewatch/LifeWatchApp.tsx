import React, { useState, useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from './layout/Sidebar';
import { ChatPanel, ChatDisplayMode } from '../../core/components/Chatbot';

// Pages
import Home from './pages/home/Home';
import Timeline from './pages/timeline/Timeline';
import CategoryPage from './pages/category/CategoryPage';
import ReportsPage from './pages/reports/ReportsPage';
import UsagePage from './pages/usage/UsagePage';

export const LifeWatchApp: React.FC = () => {
    const [chatDisplayMode, setChatDisplayMode] = useState<ChatDisplayMode>('hidden');
    const [chatPanelWidth, setChatPanelWidth] = useState(0); // 聊天面板宽度
    const [isLargeScreen, setIsLargeScreen] = useState(false); // 是否为大屏幕
    const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false); // 侧边栏折叠状态

    // 监听屏幕尺寸变化
    useEffect(() => {
        const checkScreenSize = () => {
            // lg breakpoint is 1024px in Tailwind
            setIsLargeScreen(window.innerWidth >= 1024);
        };

        checkScreenSize();
        window.addEventListener('resize', checkScreenSize);
        return () => window.removeEventListener('resize', checkScreenSize);
    }, []);

    return (
        <>
            {/* Navigation (Left Sidebar) */}
            <Sidebar
                onChatToggle={() => setChatDisplayMode(prev => prev === 'hidden' ? 'sidebar' : 'hidden')}
                isCollapsed={isSidebarCollapsed}
                onToggle={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
            />

            {/* Main Content Area (Center) */}
            <main
                className={`p-6 lg:p-10 min-h-screen transition-all duration-300 ease-in-out ${isSidebarCollapsed ? 'lg:ml-20' : 'lg:ml-64'}`}
                style={{ marginRight: isLargeScreen && chatPanelWidth > 0 ? `${chatPanelWidth}px` : undefined }}
            >
                <Routes>
                    <Route path="/" element={<Home />} />
                    <Route path="/home" element={<Navigate to="/" replace />} />
                    <Route path="/timeline" element={<Timeline />} />
                    <Route path="/category" element={<CategoryPage />} />
                    <Route path="/reports" element={<ReportsPage />} />
                    <Route path="/usage" element={<UsagePage />} />
                    {/* Fallback */}
                    <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
            </main>

            {/* AI Chat (Right Sidebar) */}
            <ChatPanel
                displayMode={chatDisplayMode}
                onModeChange={setChatDisplayMode}
                onWidthChange={setChatPanelWidth}
            />
        </>
    );
};
