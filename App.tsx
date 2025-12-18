

import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import TimelinePage from './components/TimelinePage';
import CategorizationPage from './components/CategorizationPage';
import AIChatPanel from './components/AIChatPanel';
import { incrementalSync } from './services/syncService';
import UsagePage from './components/UsagePage';
function App() {
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [currentPage, setCurrentPage] = useState('home');
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncError, setSyncError] = useState<string | null>(null);

  // 页面加载时自动同步数据
  useEffect(() => {
    const performSync = async () => {
      setIsSyncing(true);
      setSyncError(null);

      try {
        console.log('🔄 开始自动同步数据...');
        const result = await incrementalSync();
        console.log('✅ 同步成功:', result);
        console.log(`  - 模式: ${result.details?.sync_mode}`);
        console.log(`  - 时间范围: ${result.details?.time_range}`);
        console.log(`  - 同步事件数: ${result.synced_events}`);
        console.log(`  - 新分类应用: ${result.new_apps_classified}`);
      } catch (error) {
        console.error('❌ 同步失败:', error);
        setSyncError(error instanceof Error ? error.message : '同步失败');
      } finally {
        setIsSyncing(false);
      }
    };

    performSync();
  }, []); // 空依赖数组，只在组件挂载时执行一次


  return (
    <div className="min-h-screen bg-[#F9FAFB] text-slate-800 font-sans relative">

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

      {/* Navigation (Left Sidebar) */}
      <Sidebar
        currentPage={currentPage}
        onNavigate={setCurrentPage}
        onChatToggle={() => setIsChatOpen(!isChatOpen)}
      />

      {/* Main Content Area (Center) */}
      <main
        className={`lg:ml-64 p-6 lg:p-10 min-h-screen transition-all duration-300 ease-in-out ${isChatOpen ? 'lg:mr-[400px]' : ''
          }`}
      >
        {currentPage === 'home' && <Dashboard />}
        {currentPage === 'timeline' && <TimelinePage />}
        {currentPage === 'categorization' && <CategorizationPage />}

        {/* Fallback for pages not yet implemented */}
        {!['home', 'timeline', 'categorization'].includes(currentPage) && (
          <div className="flex flex-col items-center justify-center h-[60vh] text-center animate-fade-in">
            <h2 className="text-2xl font-bold text-slate-300 mb-2">Coming Soon</h2>
            <p className="text-slate-400">The {currentPage} module is currently under development.</p>
            <button
              onClick={() => setCurrentPage('home')}
              className="mt-6 px-6 py-2 bg-white border border-gray-200 rounded-xl text-slate-600 font-medium hover:bg-gray-50 transition-colors"
            >
              Return Home
            </button>
          </div>
        )}
      </main>

      {/* AI Chat (Right Sidebar) */}
      <AIChatPanel isOpen={isChatOpen} onClose={() => setIsChatOpen(false)} />

    </div>
  );
}

export default App;
