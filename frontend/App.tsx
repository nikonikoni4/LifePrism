import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { AppShell } from './shell/AppShell';
import { FloatingRouter } from './floating/FloatingRouter';
import { DialogRouter } from './dialogs/DialogRouter';
import { incrementalSync } from './core/services/syncService';
import { initApiConfig, getApiV2UrlSync } from './core/services/apiConfig';
import { initPlanDocBridge } from './core/services/ipcPlanDocBridge';
import { toast } from './core/components';
import DataPathWarningDialog from './core/components/DataPathWarningDialog';
import UpdateNotification from './core/components/UpdateNotification';
import { UserInfoProvider } from './core/context/UserInfoContext';
import { DemoDialog } from './src/components/DemoDialog';
import { isDemoMode } from './src/config/env';

function MainApp() {
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [isApiReady, setIsApiReady] = useState(false);
  const [pathWarnings, setPathWarnings] = useState<string[]>([]);
  const [showDemoDialog, setShowDemoDialog] = useState(false);

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

  // 初始化 PlanDoc IPC 桥接（主窗口监听浮窗的同步请求）
  useEffect(() => {
    initPlanDocBridge();
  }, []);

  // 启动时请求系统警告
  useEffect(() => {
    if (!isApiReady) return;
    fetch(`${getApiV2UrlSync()}/system/warnings`)
      .then(res => res.ok ? res.json() : null)
      .catch(() => null)
      .then(data => {
        if (data?.warnings?.length) {
          const pathMsgs: string[] = [];
          data.warnings.forEach((w: { type: string; message: string }) => {
            if (w.type === 'data_path') {
              pathMsgs.push(w.message);
            } else {
              toast.warning(w.message, 10000);
            }
          });
          if (pathMsgs.length > 0) {
            setPathWarnings(pathMsgs);
          }
        }
      });
  }, [isApiReady]);

  // Demo 模式：首次访问显示引导弹窗
  useEffect(() => {
    if (isDemoMode && !sessionStorage.getItem('demo-dialog-shown')) {
      setShowDemoDialog(true);
    }
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
      })
      .catch(error => {
        console.error('❌ 后台同步失败:', error);
        setSyncError(error instanceof Error ? error.message : '同步失败');
        toast.error(error instanceof Error ? error.message : '同步失败');
      })
      .finally(() => {
        setIsSyncing(false);
      });
  }, [isApiReady]);

  return (
    <>
      {/* 全局同步状态指示器 */}
      {isSyncing && (
        <div className="fixed top-0 left-0 right-0 z-[10000] bg-blue-500 text-white px-4 py-2 text-center text-sm font-medium shadow-lg pointer-events-none">
          <span className="inline-flex items-center">
            <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            正在同步数据...
          </span>
        </div>
      )}

      {/* 等待 API 配置初始化完成后再渲染 Shell */}
      {!isApiReady ? (
        <div className="flex items-center justify-center h-screen bg-[#F9FAFB]">
          <div className="text-center">
            <svg className="animate-spin h-12 w-12 text-blue-500 mx-auto mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <p className="text-slate-500 font-medium">正在连接后端服务...</p>
          </div>
        </div>
      ) : (
        <AppShell />
      )}

      {pathWarnings.length > 0 && (
        <DataPathWarningDialog
          warnings={pathWarnings}
          onClose={() => setPathWarnings([])}
        />
      )}

      {/* Demo 模式引导弹窗 */}
      {showDemoDialog && (
        <DemoDialog onClose={() => setShowDemoDialog(false)} />
      )}

      <UpdateNotification />
    </>
  );
}

function App() {
  const location = useLocation();

  // 浮窗路由分流：跳过主窗口的 API 初始化、同步等逻辑
  if (location.pathname.startsWith('/floating/')) {
    return <FloatingRouter />;
  }

  // 对话框路由分流：独立的对话框窗口
  if (location.pathname.startsWith('/dialog/')) {
    return <DialogRouter />;
  }

  return (
    <UserInfoProvider>
      <MainApp />
    </UserInfoProvider>
  );
}

export default App;
