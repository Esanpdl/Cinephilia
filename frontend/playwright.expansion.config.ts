import { defineConfig } from '@playwright/test'
import core from './playwright.config'

export default defineConfig(core, {
  testMatch: 'expansion.spec.ts',
  timeout: 180_000,
  reporter: [['list'], ['json', { outputFile: '../data/expansion/browser-results.json' }]],
})
