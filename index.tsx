import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { initCacheCleanup } from './utils/cacheManager';
import './src/styles/main.css';

// 初始化缓存清理
initCacheCleanup();

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error("Could not find root element to mount to");
}

const root = ReactDOM.createRoot(rootElement);
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);