/**
 * Demo 演示模式引导弹窗
 *
 * 功能：
 * - 首次访问时自动弹出
 * - 展示项目信息、投票链接、只读限制说明
 * - 支持"不再提示本次会话"选项
 */

import { useState } from 'react';
import { X } from 'lucide-react';

interface DemoDialogProps {
  onClose: () => void;
}

export const DemoDialog: React.FC<DemoDialogProps> = ({ onClose }) => {
  const [dontShowAgain, setDontShowAgain] = useState(false);

  const handleClose = () => {
    if (dontShowAgain) {
      sessionStorage.setItem('demo-dialog-shown', 'true');
    }
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="relative w-full max-w-4xl mx-4 max-h-[90vh] overflow-y-auto bg-white rounded-lg shadow-xl">
        {/* 关闭按钮 */}
        <button
          onClick={handleClose}
          className="absolute top-4 right-4 z-10 text-gray-400 hover:text-gray-600 transition-colors"
          aria-label="关闭"
        >
          <X size={24} />
        </button>

        {/* 内容区域 */}
        <div className="p-8">
          {/* 标题 */}
          <div className="mb-6">
            <h2 className="text-2xl font-semibold text-gray-900 mb-2">
              欢迎体验 LifePrism Demo
            </h2>
            <p className="text-sm text-gray-500">
              这是一个在线演示环境，让您快速了解 LifePrism 的功能
            </p>
          </div>

          {/* 左右两栏布局 */}
          <div className="flex flex-col md:flex-row gap-5 mb-6">
            {/* 左栏：模块导航说明图 */}
            <div className="md:w-1/2 flex-shrink-0">
              <div className="p-4 bg-gray-50 rounded-lg h-full">
                <h3 className="text-sm font-semibold text-gray-900 mb-3">📱 模块导航栏</h3>
                <p className="text-sm text-gray-600 mb-3">
                  顶部工具栏可切换不同功能模块：
                  <strong>LifeWatch</strong>（活动追踪）、目标管理、快捷操作等。
                </p>
                <img
                  src="/模块导航栏说明.png"
                  alt="模块导航栏位置说明"
                  className="w-full rounded-lg border border-gray-200"
                  style={{ maxHeight: '300px', objectFit: 'contain' }}
                />
              </div>
            </div>

            {/* 右栏：信息卡片 */}
            <div className="md:w-1/2 space-y-3">
              {/* GitHub 链接 */}
              <div className="p-4 bg-blue-50 rounded-lg">
                <h3 className="text-sm font-semibold text-blue-900 mb-1">🚀 开源项目</h3>
                <p className="text-sm text-blue-800 mb-1">
                  LifePrism 是一个开源的数据驱动自我成长平台
                </p>
                <a
                  href="https://github.com/nikonikoni4/LifePrism"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-block text-sm text-blue-600 hover:text-blue-700 font-medium underline"
                >
                  访问 GitHub 仓库 →
                </a>
              </div>

              {/* 投票链接 */}
              <div className="p-4 bg-purple-50 rounded-lg">
                <h3 className="text-sm font-semibold text-purple-900 mb-1">🏆 参与投票</h3>
                <p className="text-sm text-purple-800 mb-1">
                  正在参加创造力大赛，欢迎为我们投票支持！
                </p>
                <a
                  href="https://forum.trae.cn/t/topic/70390"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-block text-sm text-purple-600 hover:text-purple-700 font-medium underline"
                >
                  前往投票页面 →
                </a>
              </div>

              {/* 只读限制说明 */}
              <div className="p-4 bg-amber-50 rounded-lg">
                <h3 className="text-sm font-semibold text-amber-900 mb-1">⚠️ 只读演示</h3>
                <p className="text-sm text-amber-800">
                  当前 Demo 环境为<strong>只读模式</strong>，无法保存数据修改。如需完整体验，请到 GitHub 下载本地安装。
                </p>
              </div>
            </div>
          </div>

          {/* 复选框 */}
          <div className="flex items-center mb-6">
            <input
              id="dont-show-again"
              type="checkbox"
              checked={dontShowAgain}
              onChange={(e) => setDontShowAgain(e.target.checked)}
              className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-2 focus:ring-blue-500"
            />
            <label htmlFor="dont-show-again" className="ml-2 text-sm text-gray-700">
              本次会话不再提示
            </label>
          </div>

          {/* 按钮 */}
          <div className="flex justify-center">
            <button
              onClick={handleClose}
              className="px-10 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors font-medium"
            >
              开始体验
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
