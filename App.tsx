

import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import { ModuleDock, ModuleId } from './components/ModuleDock';

import Timeline from './page/timeline/Timeline';
import { ChatPanel, ChatDisplayMode } from './page/chatbot';
import { incrementalSync } from './services/syncService';
import { initApiConfig, isApiConfigInitialized } from './services/apiConfig';
import UsagePage from './page/usage/UsagePage';
import Home from './page/home/Home';
import CategoryPage from './page/category/CategoryPage';
import GoalsPage from './page/goals/GoalsPage';
import { GoalPage } from './page/goalsV2/GoalPage';
import { HabitPage } from './page/habits/HabitPage';
import ReportsPage from './page/reports/ReportsPage';
import SettingsPage from './page/settings/SettingsPage';
import { ToastContainer } from './page/common';


function App() {
  // 模块切换状态
  const [currentModule, setCurrentModule] = useState<ModuleId>('lifewatch');
  
  const [chatDisplayMode, setChatDisplayMode] = useState<ChatDisplayMode>('hidden');
  const [chatPanelWidth, setChatPanelWidth] = useState(0); // 聊天面板宽度
  const [isLargeScreen, setIsLargeScreen] = useState(false); // 是否为大屏幕
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false); // 侧边栏折叠状态
  const [currentPage, setCurrentPage] = useState('home');
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [isApiReady, setIsApiReady] = useState(false);

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

  // 初始化 API 配置（探测后端端口）
  useEffect(() => {
    console.log('🔧 初始化 API 配置...');
    initApiConfig()
      .then((baseUrl) => {
        console.log(`✅ API 配置初始化完成，后端地址: ${baseUrl}`);
        setIsApiReady(true);
      })
      .catch((error) => {
        console.error('❌ API 配置初始化失败:', error);
        // 即使失败也设置为 ready，使用默认端口
        setIsApiReady(true);
      });
  }, []);

  // 页面加载时自动同步数据（等待 API 配置初始化完成）
  useEffect(() => {
    // 等待 API 配置初始化完成
    if (!isApiReady) {
      return;
    }

    // 后台同步，不阻塞页面渲染
    console.log('🔄 开始后台同步数据...');
    setIsSyncing(true);

    incrementalSync()
      .then(result => {
        console.log('✅ 后台同步成功:', result);
        console.log(`  - 模式: ${result.details?.sync_mode}`);
        console.log(`  - 时间范围: ${result.details?.time_range}`);
        console.log(`  - 同步事件数: ${result.synced_events}`);
        console.log(`  - 新分类应用: ${result.new_apps_classified}`);
      })
      .catch(error => {
        console.error('❌ 后台同步失败:', error);
        setSyncError(error instanceof Error ? error.message : '同步失败');
      })
      .finally(() => {
        setIsSyncing(false);
      });
  }, [isApiReady]); // 依赖 isApiReady，API 准备好后开始同步


  return (
    <div className="min-h-screen bg-[#F9FAFB] text-slate-800 font-sans relative">

      {/* 顶部悬浮模块切换 Dock */}
      <ModuleDock 
        currentModule={currentModule} 
        onModuleChange={setCurrentModule} 
      />

      {/* 同步状态指示器 */}
      {isSyncing && (
        <div className="fixed top-0 left-0 right-0 z-50 bg-blue-500 text-white px-4 py-2 text-center text-sm font-medium shadow-lg">
          <span className="inline-flex items-center">
            <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            正在同步数据...
          </span>
        </div>
      )}

      {/* 同步错误提示 */}
      {syncError && (
        <div className="fixed top-0 left-0 right-0 z-50 bg-red-500 text-white px-4 py-2 text-center text-sm font-medium shadow-lg">
          <span className="inline-flex items-center">
            <svg className="mr-2 h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
            同步失败: {syncError}
          </span>
        </div>
      )}

      {/* Navigation (Left Sidebar) - 仅在 LifeWatch 模块显示 */}
      {currentModule === 'lifewatch' && (
        <Sidebar
          currentPage={currentPage}
          onNavigate={setCurrentPage}
          onChatToggle={() => setChatDisplayMode(prev => prev === 'hidden' ? 'sidebar' : 'hidden')}
          isCollapsed={isSidebarCollapsed}
          onToggle={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
        />
      )}

      {/* Main Content Area (Center) */}
      {currentModule === 'lifewatch' && (
        <main
          className={`p-6 lg:p-10 min-h-screen transition-all duration-300 ease-in-out ${isSidebarCollapsed ? 'lg:ml-20' : 'lg:ml-64'}`}
          style={{ marginRight: isLargeScreen && chatPanelWidth > 0 ? `${chatPanelWidth}px` : undefined }}
        >
          {/* 等待 API 配置初始化完成后再渲染页面内容 */}
          {!isApiReady ? (
            <div className="flex items-center justify-center h-screen">
              <div className="text-center">
                <svg className="animate-spin h-12 w-12 text-blue-500 mx-auto mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <p className="text-slate-500 font-medium">正在连接后端服务...</p>
              </div>
            </div>
          ) : (
            <>
              {currentPage === 'home' && <Home onNavigate={setCurrentPage} />}
              {currentPage === 'timeline' && <Timeline />}
              {currentPage === 'category' && <CategoryPage />}
              {currentPage === 'goals' && <GoalsPage />}
              {currentPage === 'goalsV2' && <GoalPage />}
              {currentPage === 'habits' && <HabitPage />}
              {currentPage === 'reports' && <ReportsPage />}
              {currentPage === 'usage' && <UsagePage />}

              {currentPage === 'settings' && <SettingsPage />}
            </>
          )}
        </main>
      )}

      {/* MindSpace 模块 - 占位内容 */}
      {currentModule === 'mindspace' && (
        <main className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
          <div className="text-center">
            <div className="w-24 h-24 mx-auto mb-6 rounded-full bg-gradient-to-br from-pink-500 to-purple-600 flex items-center justify-center shadow-2xl shadow-purple-500/30">
              <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.5" className="w-12 h-12">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z" />
                <path d="M12 8c-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4-1.79-4-4-4z" />
              </svg>
            </div>
            <h1 className="text-4xl font-bold text-white mb-3">MindSpace</h1>
            <p className="text-purple-200/70 text-lg">心理与情绪空间</p>
            <p className="text-purple-300/50 text-sm mt-4">即将推出...</p>
          </div>
        </main>
      )}

      {/* Add-ons 模块 - 占位内容 */}
      {currentModule === 'addons' && (
        <main className="min-h-screen flex items-center justify-center bg-gradient-to-br from-emerald-50 to-teal-100">
          <div className="text-center">
            <div className="w-24 h-24 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-2xl shadow-emerald-500/30">
              <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.5" className="w-12 h-12">
                <rect x="3" y="3" width="7" height="7" rx="1" />
                <rect x="14" y="3" width="7" height="7" rx="1" />
                <rect x="3" y="14" width="7" height="7" rx="1" />
                <path d="M17.5 14v7" />
                <path d="M14 17.5h7" />
              </svg>
            </div>
            <h1 className="text-4xl font-bold text-emerald-900 mb-3">Add-ons</h1>
            <p className="text-emerald-600/70 text-lg">扩展插件中心</p>
            <p className="text-emerald-500/50 text-sm mt-4">即将推出...</p>
          </div>
        </main>
      )}

      {/* AI Chat (Right Sidebar) - 仅在 LifeWatch 模块显示 */}
      {currentModule === 'lifewatch' && (
        <ChatPanel
          displayMode={chatDisplayMode}
          onModeChange={setChatDisplayMode}
          onWidthChange={setChatPanelWidth}
        />
      )}

      {/* Toast 消息容器 */}
      <ToastContainer />

    </div>
  );
}

export default App;
