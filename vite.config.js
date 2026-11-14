import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    ...(process.env.FIGMA && process.env.FIGMA_PUBLIC_URL
      ? { allowedHosts: [new URL(process.env.FIGMA_PUBLIC_URL).hostname] }
      : {}),
  },
  test: { include: ['web-app/src/**/*.test.js'] },
});
