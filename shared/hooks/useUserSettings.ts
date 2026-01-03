/**
 * User Settings Hook
 * 
 * 使用 LocalStorage 保存和读取用户设置的 React Hook
 */

import { useState, useEffect } from 'react';
import { reportCache } from '../../services/reportCacheService';

/**
 * 用户设置接口
 */
export interface UserSettings {
    // 界面设置
    theme: 'light' | 'dark';
    language: 'zh-CN' | 'en-US';

    // 报告设置
    defaultReportView: 'daily' | 'weekly' | 'monthly';
    chartType: 'line' | 'area' | 'bar';
    showTodoStats: boolean;
    showGoalProgress: boolean;

    // 通知设置
    enableNotifications: boolean;
    notificationTime: string; // HH:mm 格式

    // 其他设置
    autoRefresh: boolean;
    refreshInterval: number; // 分钟
}

/**
 * 默认设置
 */
const DEFAULT_SETTINGS: UserSettings = {
    theme: 'light',
    language: 'zh-CN',
    defaultReportView: 'daily',
    chartType: 'line',
    showTodoStats: true,
    showGoalProgress: true,
    enableNotifications: false,
    notificationTime: '09:00',
    autoRefresh: false,
    refreshInterval: 30,
};

/**
 * 使用用户设置的 Hook
 */
export function useUserSettings() {
    const [settings, setSettings] = useState<UserSettings>(() => {
        // 从缓存加载设置
        const cached = reportCache.settings.get<UserSettings>('userSettings');
        return cached || DEFAULT_SETTINGS;
    });

    // 更新设置
    const updateSettings = (newSettings: Partial<UserSettings>) => {
        setSettings(prev => {
            const updated = { ...prev, ...newSettings };
            // 保存到缓存
            reportCache.settings.set('userSettings', updated);
            return updated;
        });
    };

    // 重置为默认设置
    const resetSettings = () => {
        setSettings(DEFAULT_SETTINGS);
        reportCache.settings.set('userSettings', DEFAULT_SETTINGS);
    };

    return {
        settings,
        updateSettings,
        resetSettings,
    };
}

/**
 * 使用单个设置项的 Hook
 */
export function useSetting<K extends keyof UserSettings>(
    key: K
): [UserSettings[K], (value: UserSettings[K]) => void] {
    const { settings, updateSettings } = useUserSettings();

    const setValue = (value: UserSettings[K]) => {
        updateSettings({ [key]: value } as Partial<UserSettings>);
    };

    return [settings[key], setValue];
}

/**
 * 使用示例:
 * 
 * // 1. 使用所有设置
 * const { settings, updateSettings, resetSettings } = useUserSettings();
 * 
 * // 2. 使用单个设置
 * const [theme, setTheme] = useSetting('theme');
 * setTheme('dark');
 * 
 * // 3. 批量更新设置
 * updateSettings({
 *     theme: 'dark',
 *     language: 'en-US',
 *     chartType: 'area',
 * });
 */
