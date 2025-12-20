/**
 * Reports Page API
 * 
 * 报告统计相关接口（占位）
 */

import { ReportResponse, DateRangeType } from './types';

const API_BASE = 'http://localhost:8000/api/v2';

/**
 * Reports API
 */
export const ReportsAPI = {
    /**
     * 获取报告数据
     */
    async getReport(params: {
        type: DateRangeType;
        startDate?: string;
        endDate?: string;
    }): Promise<ReportResponse> {
        // TODO: 实现真实 API 调用
        throw new Error('Not implemented');
    },

    /**
     * 导出报告
     */
    async exportReport(params: {
        type: DateRangeType;
        format: 'pdf' | 'csv' | 'json';
        startDate?: string;
        endDate?: string;
    }): Promise<Blob> {
        // TODO: 实现真实 API 调用
        throw new Error('Not implemented');
    },
};
