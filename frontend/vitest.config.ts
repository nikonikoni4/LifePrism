import path from 'path';
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, '.'),
      '@my-ui-kit/core': path.resolve(__dirname, './my-ui-kit/ui-kit/index.ts'),
      // Force single React instance to avoid "Invalid hook call" when importing
      // components from my-ui-kit (which has its own node_modules/react)
      'react': path.resolve(__dirname, './node_modules/react'),
      'react-dom': path.resolve(__dirname, './node_modules/react-dom'),
      // Force single @dnd-kit instance so vi.mock() in tests intercepts imports
      // from both frontend and my-ui-kit code paths.
      '@dnd-kit/sortable': path.resolve(__dirname, './node_modules/@dnd-kit/sortable'),
      '@dnd-kit/utilities': path.resolve(__dirname, './node_modules/@dnd-kit/utilities'),
      '@dnd-kit/core': path.resolve(__dirname, './node_modules/@dnd-kit/core'),
    },
    // Dedupe ensures transitive deps (e.g. @dnd-kit inside my-ui-kit) also
    // resolve to the single React instance declared by the alias above.
    dedupe: ['react', 'react-dom'],
  },
  test: {
    include: ['**/*.test.ts', '**/*.test.tsx'],
    exclude: ['node_modules', 'dist', 'build', 'my-ui-kit/**'],
    environment: 'jsdom',
    setupFiles: ['./test-setup.ts'],
    server: {
      deps: {
        // Inline my-ui-kit and @dnd-kit so Vite transforms them and the
        // resolve.alias / dedupe above apply to their `import 'react'`.
        inline: [/my-ui-kit/, /@dnd-kit/],
      },
    },
  },
});
