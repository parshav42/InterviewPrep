import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://127.0.0.1:5500',
    browserName: 'chromium',
    launchOptions: {
      args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream']
    },
    permissions: ['camera', 'microphone']
  },
  webServer: process.env.E2E_WEB_SERVER ? {
    command: process.env.E2E_WEB_SERVER,
    url: 'http://127.0.0.1:5500/index.html',
    reuseExistingServer: true
  } : undefined,
  reporter: [['list']]
});
