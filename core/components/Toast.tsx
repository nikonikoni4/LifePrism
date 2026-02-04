/**
 * Toast - 通用消息弹出组件
 *
 * 从上方弹出，设定时间后自动消失
 */

import React, { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { CheckCircle, XCircle, AlertCircle, Info, X } from 'lucide-react';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface ToastMessage {
    id: string;
    type: ToastType;
    message: string;
    duration?: number;
}

interface ToastItemProps {
    toast: ToastMessage;
    onClose: (id: string) => void;
}

const toastConfig = {
    success: {
        icon: CheckCircle,
        bgColor: 'bg-green-50',
        borderColor: 'border-green-200',
        textColor: 'text-green-800',
        iconColor: 'text-green-500',
    },
    error: {
        icon: XCircle,
        bgColor: 'bg-red-50',
        borderColor: 'border-red-200',
        textColor: 'text-red-800',
        iconColor: 'text-red-500',
    },
    warning: {
        icon: AlertCircle,
        bgColor: 'bg-amber-50',
        borderColor: 'border-amber-200',
        textColor: 'text-amber-800',
        iconColor: 'text-amber-500',
    },
    info: {
        icon: Info,
        bgColor: 'bg-blue-50',
        borderColor: 'border-blue-200',
        textColor: 'text-blue-800',
        iconColor: 'text-blue-500',
    },
};

const ToastItem: React.FC<ToastItemProps> = ({ toast, onClose }) => {
    const [isVisible, setIsVisible] = useState(false);
    const [isLeaving, setIsLeaving] = useState(false);
    const config = toastConfig[toast.type];
    const Icon = config.icon;

    useEffect(() => {
        // 触发进入动画
        requestAnimationFrame(() => setIsVisible(true));

        const duration = toast.duration ?? 3000;
        const timer = setTimeout(() => {
            setIsLeaving(true);
            setTimeout(() => onClose(toast.id), 300);
        }, duration);

        return () => clearTimeout(timer);
    }, [toast.id, toast.duration, onClose]);

    const handleClose = () => {
        setIsLeaving(true);
        setTimeout(() => onClose(toast.id), 300);
    };

    return (
        <div
            className={`
                flex items-center gap-3 px-4 py-3 rounded-xl border shadow-lg
                ${config.bgColor} ${config.borderColor}
                transition-all duration-300 ease-out
                ${isVisible && !isLeaving ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-4'}
            `}
        >
            <Icon size={20} className={config.iconColor} />
            <span className={`text-sm font-medium ${config.textColor} flex-1`}>
                {toast.message}
            </span>
            <button
                onClick={handleClose}
                className={`p-1 rounded-full hover:bg-black/5 transition-colors ${config.textColor}`}
            >
                <X size={14} />
            </button>
        </div>
    );
};

// 全局 Toast 状态管理
type ToastListener = (toasts: ToastMessage[]) => void;

class ToastManager {
    private toasts: ToastMessage[] = [];
    private listeners: Set<ToastListener> = new Set();

    subscribe(listener: ToastListener) {
        this.listeners.add(listener);
        return () => this.listeners.delete(listener);
    }

    private notify() {
        this.listeners.forEach(listener => listener([...this.toasts]));
    }

    show(type: ToastType, message: string, duration?: number) {
        const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
        this.toasts.push({ id, type, message, duration });
        this.notify();
        return id;
    }

    remove(id: string) {
        this.toasts = this.toasts.filter(t => t.id !== id);
        this.notify();
    }

    success(message: string, duration?: number) {
        return this.show('success', message, duration);
    }

    error(message: string, duration?: number) {
        return this.show('error', message, duration);
    }

    warning(message: string, duration?: number) {
        return this.show('warning', message, duration);
    }

    info(message: string, duration?: number) {
        return this.show('info', message, duration);
    }
}

export const toastManager = new ToastManager();

// 便捷函数
export const toast = {
    success: (message: string, duration?: number) => toastManager.success(message, duration),
    error: (message: string, duration?: number) => toastManager.error(message, duration),
    warning: (message: string, duration?: number) => toastManager.warning(message, duration),
    info: (message: string, duration?: number) => toastManager.info(message, duration),
};

// Toast 容器组件 - 需要在 App 根组件中渲染一次
export const ToastContainer: React.FC = () => {
    const [toasts, setToasts] = useState<ToastMessage[]>([]);

    useEffect(() => {
        const unsubscribe = toastManager.subscribe(setToasts);
        return () => { unsubscribe(); };
    }, []);

    const handleClose = useCallback((id: string) => {
        toastManager.remove(id);
    }, []);

    if (toasts.length === 0) return null;

    return createPortal(
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 flex flex-col gap-2 pointer-events-none">
            {toasts.map(t => (
                <div key={t.id} className="pointer-events-auto">
                    <ToastItem toast={t} onClose={handleClose} />
                </div>
            ))}
        </div>,
        document.body
    );
};

export default ToastContainer;
