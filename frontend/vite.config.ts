import path from 'path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  return {
    base: './',
    server: {
      port: 8100,
      host: '0.0.0.0',
      proxy: {
        '/api': {
          target: 'http://localhost:8101',
          changeOrigin: true,
          secure: false,
        },
      },
      watch: {
        // 排除 lifeprismData 目录，避免后端写入 md 文件时触发热重载
        ignored: ['**/lifeprismData/**'],
      },
    },
    plugins: [react(), tailwindcss()],
    define: {
      'process.env.API_KEY': JSON.stringify(env.GEMINI_API_KEY),
      'process.env.GEMINI_API_KEY': JSON.stringify(env.GEMINI_API_KEY)
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
        '@my-ui-kit/core': path.resolve(__dirname, './my-ui-kit/ui-kit'),
        // Force single React instance to avoid "Invalid hook call" errors
        'react': path.resolve(__dirname, './node_modules/react'),
        'react-dom': path.resolve(__dirname, './node_modules/react-dom'),
      }
    }
  };
});
