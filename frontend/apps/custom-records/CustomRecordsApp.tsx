/**
 * 自定义记录模块入口
 * 顶级独立模块，与 habits/goals 同层级
 * 内部使用状态驱动视图切换（参考 HabitsApp 模式）
 */
import React, { useState, useCallback } from 'react';
import { TypeListView } from './components/TypeListView';
import { CreateTypeView } from './components/CreateTypeView';
import { TypeDetailView } from './components/TypeDetailView';

type ViewState =
  | { view: 'list' }
  | { view: 'create' }
  | { view: 'detail'; typeId: string };

export const CustomRecordsApp: React.FC = () => {
  const [viewState, setViewState] = useState<ViewState>({ view: 'list' });
  const [refreshKey, setRefreshKey] = useState(0);

  const goToCreate = useCallback(() => setViewState({ view: 'create' }), []);
  const goToDetail = useCallback((typeId: string) => setViewState({ view: 'detail', typeId }), []);
  const goToList = useCallback(() => {
    setViewState({ view: 'list' });
    setRefreshKey(k => k + 1);
  }, []);

  return (
    <div className="min-h-screen pt-16 pb-20">
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
    </div>
  );
};
