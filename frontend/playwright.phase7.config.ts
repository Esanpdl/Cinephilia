import { defineConfig } from '@playwright/test'
import core from './playwright.config'

export default defineConfig(core, {
  testMatch: 'phase7.spec.ts',
  reporter: [['list'], ['json', { outputFile: '../data/phase7/browser-results.json' }]],
})
