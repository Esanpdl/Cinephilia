import { chromium } from '@playwright/test'
import fs from 'node:fs'

const browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE })
const report = { checked_at: new Date().toISOString(), views: [], failures: [], responses: [], errors: [] }
try {
  const page = await browser.newPage()
  page.on('requestfailed', request => { if (request.url().includes('letterboxd')) report.failures.push({ url: request.url(), error: request.failure()?.errorText }) })
  page.on('response', response => { if (response.url().includes('letterboxd')) report.responses.push({ url: response.url(), status: response.status(), headers: response.headers() }) })
  page.on('console', message => { if (message.type() === 'error') report.errors.push(message.text()) })
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    await page.goto('http://127.0.0.1:5173/films/238')
    const iframe = page.locator('.letterboxd-rating iframe')
    await iframe.waitFor()
    await iframe.scrollIntoViewIfNeeded()
    const frame = await (await iframe.elementHandle()).contentFrame()
    await frame.waitForLoadState('domcontentloaded', { timeout: 45000 })
    await page.waitForTimeout(2000)
    const result = await frame.evaluate(() => ({
      url: location.href, title: document.title,
      text: document.body.innerText.slice(0, 600),
      bodyHeight: document.body.scrollHeight,
      viewportHeight: innerHeight,
      links: Array.from(document.querySelectorAll('a')).map(a => ({ text: a.textContent?.trim(), href: a.href })),
    }))
    report.views.push({ width, ...result, src: await iframe.getAttribute('src'), overflow: await page.evaluate(() => document.documentElement.scrollWidth > innerWidth) })
    await page.locator('.letterboxd-rating').screenshot({ path: '../data/expansion/screenshots/letterboxd-' + width + '.png' })
  }
} finally {
  fs.writeFileSync('../data/expansion/letterboxd-browser-check.json', JSON.stringify(report, null, 2))
  console.log(JSON.stringify(report, null, 2))
  await browser.close()
}
