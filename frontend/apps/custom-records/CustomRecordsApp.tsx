/**
 * 自定义记录模块入口
 * 顶级独立模块，与 habits/goals 同层级
 * 内部使用状态驱动视图切换（参考 HabitsApp 模式）
 * 集成 AI 助手面板（ChatPanel），支持通过 AI 录入数据
 */
import React, { useState, useCallback, useEffect } from 'react';
import { MessageCircle } from 'lucide-react';
import { TypeListView } from './components/TypeListView';
import { CreateTypeView } from './components/CreateTypeView';
import { TypeDetailView } from './components/TypeDetailView';
import { ChatPanel, ChatDisplayMode } from '../../core/components/Chatbot';

type ViewState =
  | { view: 'list' }
  | { view: 'create' }
  | { view: 'detail'; typeId: string };

export const CustomRecordsApp: React.FC = () => {
  const [viewState, setViewState] = useState<ViewState>({ view: 'list' });
  const [refreshKey, setRefreshKey] = useState(0);

  // AI 助手面板状态
  const [chatDisplayMode, setChatDisplayMode] = useState<ChatDisplayMode>('hidden');
  const [chatPanelWidth, setChatPanelWidth] = useState(0);
  const [isLargeScreen, setIsLargeScreen] = useState(false);

  // 监听屏幕尺寸变化
  useEffect(() => {
    const checkScreenSize = () => {
      setIsLargeScreen(window.innerWidth >= 1024);
    };
    checkScreenSize();
    window.addEventListener('resize', checkScreenSize);
    return () => window.removeEventListener('resize', checkScreenSize);
  }, []);

  const goToCreate = useCallback(() => setViewState({ view: 'create' }), []);
  const goToDetail = useCallback((typeId: string) => setViewState({ view: 'detail', typeId }), []);
  const goToList = useCallback(() => {
    setViewState({ view: 'list' });
    setRefreshKey(k => k + 1);
  }, []);

  return (
    <>
      <div
        className="min-h-screen pt-16 pb-20 transition-all duration-300 ease-in-out"
        style={{ marginRight: isLargeScreen && chatPanelWidth > 0 ? `${chatPanelWidth}px` : undefined }}
      >
        <div className="max-w-6xl mx-auto px-6">
          {viewState.view === 'list' && (
            <TypeListView
              key={refreshKey}
              onCreate={goToCreate}
              onViewType={goToDetail}
            />
          )}
          {viewState.view === 'create' && (
            <CreateTypeView onBack={goToList} onSuccess={goToList} />
          )}
          {viewState.view === 'detail' && (
            <TypeDetailView
              typeId={viewState.typeId}
              onBack={goToList}
            />
          )}
        </div>

        {/* AI 助手浮动切换按钮 — chatPanel 隐藏时显示 */}
        {chatDisplayMode === 'hidden' && (
          <button
            onClick={() => setChatDisplayMode('sidebar')}
            className="fixed right-6 bottom-8 z-40 w-12 h-12 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 text-white shadow-lg hover:shadow-xl hover:scale-105 transition-all flex items-center justify-center group"
            title="AI 助手"
          >
            <MessageCircle size={22} className="group-hover:scale-110 transition-transform" />
          </button>
        )}
      </div>

      {/* AI 助手面板 */}
      <ChatPanel
        displayMode={chatDisplayMode}
        onModeChange={setChatDisplayMode}
        onWidthChange={setChatPanelWidth}
      />
    </>
  );
};
