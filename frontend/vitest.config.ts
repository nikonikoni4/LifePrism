import path from 'path';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  resolve: {
    alias: {
      '@': path.resolve(__dirname, '.'),
    },
  },
  test: {
    include: ['**/*.test.ts'],
    exclude: ['node_modules', 'dist', 'build', 'my-ui-kit/**'],
  },
});
