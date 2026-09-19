import { chromium } from '@playwright/test'
import fs from 'node:fs'
const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
const problems = []
page.on('response', r => { if (r.url().includes('/cinematography/frames/') && r.status() !== 200) problems.push({ url: r.url(), status: r.status() }) })
await page.goto('http://127.0.0.1:5173/students')
await page.locator('.student-film').first().waitFor()
await page.waitForFunction(() => Array.from(document.querySelectorAll('.student-spotlight img, .student-film img')).slice(0, 5).every(img => img.complete && img.naturalWidth > 0), { timeout: 60000 })
console.log(JSON.stringify(await page.locator('img').evaluateAll(images => images.map(i => ({ src: i.src, width: i.naturalWidth, height: i.naturalHeight, opacity: getComputedStyle(i).opacity }))), null, 2))
console.log(JSON.stringify(problems))
await page.screenshot({ path: '../data/phase8/screenshots/collection-loaded.png', fullPage: true })
await browser.close()
