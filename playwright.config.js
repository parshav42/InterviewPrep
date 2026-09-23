import { defineConfig, devices } from '@playwright/test';

const e2ePort = process.env.E2E_PORT || '8002';

export default defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: process.env.E2E_BASE_URL || `http://127.0.0.1:${e2ePort}`,
    browserName: 'chromium',
    launchOptions: {
      args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream']
    },
    permissions: ['camera', 'microphone']
  },
  webServer: {
    command: `cd backend && LLM_PROVIDER=mock .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port ${e2ePort}`,
    url: `http://127.0.0.1:${e2ePort}/health`,
    reuseExistingServer: true,
    timeout: 90_000
  },
  reporter: [['list']]
});
