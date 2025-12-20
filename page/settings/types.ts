/**
 * Settings Page Types
 * 
 * 设置相关类型定义
 */

/** 用户配置 */
export interface UserSettings {
    // 显示设置
    display: {
        theme: 'light' | 'dark' | 'system';
        language: 'en' | 'zh';
        dateFormat: string;
        timeFormat: '12h' | '24h';
    };
    // 通知设置
    notifications: {
        enabled: boolean;
        dailySummary: boolean;
        weeklyReport: boolean;
        goalReminders: boolean;
    };
    // 隐私设置
    privacy: {
        shareAnonymousData: boolean;
        showInactiveTime: boolean;
    };
    // 数据设置
    data: {
        syncInterval: number;  // 分钟
        retentionDays: number;  // 数据保留天数
        autoClassify: boolean;
    };
}

/** API 配置 */
export interface APIConfig {
    geminiApiKey?: string;
    activityWatchUrl: string;
}
