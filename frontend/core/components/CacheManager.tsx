/**
 * Cache Manager Component
 * 
 * 缓存管理界面组件
 * 显示缓存统计信息,并提供清除缓存的功能
 */

import React, { useState, useEffect } from 'react';
import { CacheManager } from '../utils/cacheManager';
import { ReportCacheService } from '../services/reportCacheService';

interface CacheStats {
    dailyReports: number;
    weeklyReports: number;
    monthlyReports: number;
    settings: number;
    totalSize: string;
    totalItems: number;
    expiredItems: number;
}

export const CacheManagerComponent: React.FC = () => {
    const [stats, setStats] = useState<CacheStats | null>(null);
    const [isLoading, setIsLoading] = useState(false);

    const loadStats = () => {
        const reportStats = ReportCacheService.getCacheStats();
        const generalStats = CacheManager.getStats();

        setStats({
            ...reportStats,
            totalItems: generalStats.totalItems,
            expiredItems: generalStats.expiredItems,
        });
    };

    useEffect(() => {
        loadStats();
    }, []);

    const handleClearAll = async () => {
        const confirmed = window.electronAPI?.showConfirm
            ? await window.electronAPI.showConfirm({ message: '确定要清除所有缓存吗?这将删除所有已缓存的报告数据。' })
            : confirm('确定要清除所有缓存吗?这将删除所有已缓存的报告数据。');

        if (!confirmed) return;

        setIsLoading(true);
        CacheManager.clear();
        loadStats();
        setIsLoading(false);
        if (window.electronAPI?.showAlert) {
            window.electronAPI.showAlert({ message: '已清除所有缓存' });
        } else {
            alert('已清除所有缓存');
        }
    };

    const handleClearExpired = () => {
        setIsLoading(true);
        const count = CacheManager.clearExpired();
        loadStats();
        setIsLoading(false);
        if (window.electronAPI?.showAlert) {
            window.electronAPI.showAlert({ message: `已清除 ${count} 个过期缓存项` });
        } else {
            alert(`已清除 ${count} 个过期缓存项`);
        }
    };

    const handleClearReports = async () => {
        const confirmed = window.electronAPI?.showConfirm
            ? await window.electronAPI.showConfirm({ message: '确定要清除所有报告缓存吗?' })
            : confirm('确定要清除所有报告缓存吗?');

        if (!confirmed) return;

        setIsLoading(true);
        ReportCacheService.clearAllReports();
        loadStats();
        setIsLoading(false);
        if (window.electronAPI?.showAlert) {
            window.electronAPI.showAlert({ message: '已清除所有报告缓存' });
        } else {
            alert('已清除所有报告缓存');
        }
    };
    };

    if (!stats) {
        return <div>加载中...</div>;
    }

    return (
        <div style={{
            padding: '24px',
            backgroundColor: '#f5f5f5',
            borderRadius: '8px',
            maxWidth: '600px',
            margin: '0 auto',
        }}>
            <h2 style={{ marginBottom: '20px', color: '#333' }}>缓存管理</h2>

            {/* 缓存统计 */}
            <div style={{
                backgroundColor: 'white',
                padding: '20px',
                borderRadius: '8px',
                marginBottom: '20px',
                boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
            }}>
                <h3 style={{ marginBottom: '16px', color: '#555' }}>缓存统计</h3>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                    <StatItem label="日报告" value={stats.dailyReports} />
                    <StatItem label="周报告" value={stats.weeklyReports} />
                    <StatItem label="月报告" value={stats.monthlyReports} />
                    <StatItem label="用户设置" value={stats.settings} />
                    <StatItem label="总缓存项" value={stats.totalItems} />
                    <StatItem label="过期项" value={stats.expiredItems} color="#ff6b6b" />
                    <StatItem label="总大小" value={stats.totalSize} span={2} />
                </div>
            </div>

            {/* 操作按钮 */}
            <div style={{
                backgroundColor: 'white',
                padding: '20px',
                borderRadius: '8px',
                boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
            }}>
                <h3 style={{ marginBottom: '16px', color: '#555' }}>缓存操作</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <ActionButton
                        onClick={handleClearExpired}
                        disabled={isLoading}
                        color="#4CAF50"
                    >
                        清除过期缓存
                    </ActionButton>
                    <ActionButton
                        onClick={handleClearReports}
                        disabled={isLoading}
                        color="#2196F3"
                    >
                        清除所有报告缓存
                    </ActionButton>
                    <ActionButton
                        onClick={handleClearAll}
                        disabled={isLoading}
                        color="#f44336"
                    >
                        清除所有缓存
                    </ActionButton>
                </div>
            </div>

            {/* 说明 */}
            <div style={{
                marginTop: '20px',
                padding: '16px',
                backgroundColor: '#fff3cd',
                borderRadius: '8px',
                border: '1px solid #ffc107',
            }}>
                <h4 style={{ margin: '0 0 8px 0', color: '#856404' }}>💡 提示</h4>
                <ul style={{ margin: 0, paddingLeft: '20px', color: '#856404', fontSize: '14px' }}>
                    <li>缓存会自动过期,无需手动清理</li>
                    <li>当天的报告缓存 30 分钟,历史报告缓存 24 小时</li>
                    <li>清除缓存后,下次访问会重新从服务器加载数据</li>
                    <li>应用每小时会自动清理过期缓存</li>
                </ul>
            </div>
        </div>
    );
};

// 统计项组件
const StatItem: React.FC<{
    label: string;
    value: string | number;
    color?: string;
    span?: number;
}> = ({ label, value, color = '#333', span = 1 }) => (
    <div style={{
        gridColumn: span > 1 ? `span ${span}` : 'auto',
        padding: '12px',
        backgroundColor: '#f8f9fa',
        borderRadius: '6px',
    }}>
        <div style={{ fontSize: '12px', color: '#666', marginBottom: '4px' }}>
            {label}
        </div>
        <div style={{ fontSize: '20px', fontWeight: 'bold', color }}>
            {value}
        </div>
    </div>
);

// 操作按钮组件
const ActionButton: React.FC<{
    onClick: () => void;
    disabled?: boolean;
    color: string;
    children: React.ReactNode;
}> = ({ onClick, disabled, color, children }) => (
    <button
        onClick={onClick}
        disabled={disabled}
        style={{
            padding: '12px 24px',
            backgroundColor: disabled ? '#ccc' : color,
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            fontSize: '16px',
            fontWeight: 'bold',
            cursor: disabled ? 'not-allowed' : 'pointer',
            transition: 'all 0.2s',
            opacity: disabled ? 0.6 : 1,
        }}
        onMouseEnter={(e) => {
            if (!disabled) {
                e.currentTarget.style.opacity = '0.9';
                e.currentTarget.style.transform = 'translateY(-2px)';
            }
        }}
        onMouseLeave={(e) => {
            if (!disabled) {
                e.currentTarget.style.opacity = '1';
                e.currentTarget.style.transform = 'translateY(0)';
            }
        }}
    >
        {children}
    </button>
);

export default CacheManagerComponent;
