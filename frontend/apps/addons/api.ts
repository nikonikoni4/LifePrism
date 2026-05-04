/**
 * Add-on 扩展功能 API 调用封装
 */

import { ExpandDir, ExpandDirCreate, ExpandDirListResponse } from './types';

const BASE_URL = '/api/v2/add_on';

export const AddOnAPI = {
  /**
   * 获取所有扩展文件夹
   */
  async getExpandDirs(): Promise<ExpandDir[]> {
    const response = await fetch(`${BASE_URL}/expand_dir`);
    if (!response.ok) {
      throw new Error('获取扩展文件夹失败');
    }
    const data: ExpandDirListResponse = await response.json();
    return data.expand_dirs;
  },

  /**
   * 创建扩展文件夹
   */
  async createExpandDir(data: ExpandDirCreate): Promise<ExpandDir> {
    const response = await fetch(`${BASE_URL}/expand_dir`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || '创建失败');
    }
    return response.json();
  },

  /**
   * 更新扩展文件夹
   */
  async updateExpandDir(id: string, data: ExpandDirCreate): Promise<ExpandDir> {
    const response = await fetch(`${BASE_URL}/expand_dir/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || '更新失败');
    }
    return response.json();
  },

  /**
   * 删除扩展文件夹
   */
  async deleteExpandDir(id: string): Promise<void> {
    const response = await fetch(`${BASE_URL}/expand_dir/${id}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || '删除失败');
    }
  },
};
