import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './web-app/e2e',
  use: { baseURL: 'http://localhost:3000', headless: true },
  reporter: 'list',
  outputDir: '/tmp/cyber-katam-playwright',
});
