import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle, XCircle, AlertTriangle, X } from 'lucide-react';

type ToastType = 'success' | 'error' | 'warning';

interface Toast {
    id: number;
    type: ToastType;
    message: string;
}

interface ToastContextType {
    showToast: (type: ToastType, message: string) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

let toastId = 0;

export const ToastProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [toasts, setToasts] = useState<Toast[]>([]);

    const showToast = useCallback((type: ToastType, message: string) => {
        const id = ++toastId;
        setToasts(prev => [...prev, { id, type, message }]);
        setTimeout(() => {
            setToasts(prev => prev.filter(t => t.id !== id));
        }, 3500);
    }, []);

    const dismiss = useCallback((id: number) => {
        setToasts(prev => prev.filter(t => t.id !== id));
    }, []);

    const icons: Record<ToastType, React.ReactNode> = {
        success: <CheckCircle size={16} className="text-emerald-500" />,
        error: <XCircle size={16} className="text-red-500" />,
        warning: <AlertTriangle size={16} className="text-amber-500" />,
    };

    const bgColors: Record<ToastType, string> = {
        success: 'bg-emerald-50 border-emerald-200',
        error: 'bg-red-50 border-red-200',
        warning: 'bg-amber-50 border-amber-200',
    };

    return (
        <ToastContext.Provider value={{ showToast }}>
            {children}
            {createPortal(
                <div className="fixed top-4 right-4 z-[10000] flex flex-col gap-2 pointer-events-none">
                    <AnimatePresence>
                        {toasts.map(toast => (
                            <motion.div
                                key={toast.id}
                                initial={{ opacity: 0, x: 50, scale: 0.95 }}
                                animate={{ opacity: 1, x: 0, scale: 1 }}
                                exit={{ opacity: 0, x: 50, scale: 0.95 }}
                                className={`pointer-events-auto flex items-center gap-2.5 px-4 py-3 rounded-xl border shadow-lg ${bgColors[toast.type]} max-w-[360px]`}
                            >
                                {icons[toast.type]}
                                <span className="text-sm text-slate-700 flex-1">{toast.message}</span>
                                <button onClick={() => dismiss(toast.id)} className="text-slate-400 hover:text-slate-600 shrink-0">
                                    <X size={14} />
                                </button>
                            </motion.div>
                        ))}
                    </AnimatePresence>
                </div>,
                document.body
            )}
        </ToastContext.Provider>
    );
};

export const useToast = () => {
    const context = useContext(ToastContext);
    if (!context) {
        throw new Error('useToast must be used within a ToastProvider');
    }
    return context;
};
