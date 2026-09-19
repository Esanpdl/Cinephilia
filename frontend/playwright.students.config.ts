import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './e2e', testMatch: 'students.spec.ts', workers: 1, timeout: 120_000,
  expect: { timeout: 30_000 },
  use: { baseURL: 'http://127.0.0.1:5173', browserName: 'chromium',
    launchOptions: { executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe' },
    screenshot: 'only-on-failure' },
  reporter: [['list'], ['json', { outputFile: '../data/phase8/browser-results.json' }]],
})
