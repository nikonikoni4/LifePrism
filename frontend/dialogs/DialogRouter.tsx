import React from 'react';
import { useLocation } from 'react-router-dom';
import { TodoPickerDialog } from './todo-picker/TodoPickerDialog';
import { RecordActivityDialog } from './record-activity/RecordActivityDialog';

export const DialogRouter: React.FC = () => {
    const location = useLocation();

    // 从 /dialog/xxx 中提取 dialogId
    const dialogId = location.pathname.replace('/dialog/', '');

    switch (dialogId) {
        case 'todo-picker':
            return <TodoPickerDialog />;
        case 'record-activity':
            return <RecordActivityDialog />;
        default:
            return (
                <div className="h-screen flex items-center justify-center bg-slate-900 text-white">
                    <p className="text-sm text-slate-400">未知的对话框: {dialogId}</p>
                </div>
            );
    }
};
