// Test actual responses/rendering; an iframe's load event alone is not success.
import { chromium } from '@playwright/test'
import fs from 'node:fs'

const directory = '../data/expansion'
const report = { checked_at: new Date().toISOString(), browser: 'installed Google Chrome, headless, fresh context', checks: [] }
const browser = await chromium.launch({ headless: true, executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe' })
try {
  const variants = [
    { name: 'live-film-page', title: 'The Godfather', page: 'http://127.0.0.1:5173/films/238' },
    { name: 'official-slug-format', title: 'The Godfather', src: 'https://embed.letterboxd.com/film/the-godfather/embed-histogram/?theme=dark&noTitle=true' },
    { name: 'letterboxd-own-example', title: 'The Killing of a Sacred Deer', src: 'https://embed.letterboxd.com/tmdb/399057/embed-histogram/?notitle=true' },
  ]
  for (const variant of variants) {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
    const item = { name: variant.name, responses: [], failures: [] }
    page.on('response', response => {
      if (!response.url().startsWith('https://embed.letterboxd.com/')) return
      const headers = response.headers()
      item.responses.push({ url: response.url(), status: response.status(), challenge: headers['cf-mitigated'], framePolicy: headers['x-frame-options'] })
    })
    page.on('requestfailed', request => {
      if (request.url().includes('embed.letterboxd.com')) item.failures.push(request.failure()?.errorText)
    })
    try {
      if (variant.page) await page.goto(variant.page, { waitUntil: 'domcontentloaded', timeout: 30000 })
      else {
        await page.route('http://127.0.0.1:5173/letterboxd-diagnostic', route => route.fulfill({ contentType: 'text/html', body: `<html><body style="background:#14181c;color:white"><h1>${variant.title}</h1><div class="letterboxd-rating" style="width:440px"><iframe title="Letterboxd ratings" src="${variant.src}" width="440" height="300" frameborder="0"></iframe></div></body></html>` }))
        await page.goto('http://127.0.0.1:5173/letterboxd-diagnostic', { waitUntil: 'domcontentloaded' })
      }
      const iframe = page.locator('.letterboxd-rating iframe')
      await iframe.waitFor({ timeout: 30000 })
      await iframe.scrollIntoViewIfNeeded()
      const frame = await (await iframe.elementHandle()).contentFrame()
      await frame.waitForLoadState('domcontentloaded', { timeout: 30000 })
      await page.waitForTimeout(1500)
      item.frame = await frame.evaluate(() => ({ url: location.href, title: document.title, text: document.body.innerText.slice(0, 600), html: document.body.innerHTML.slice(0, 15000), height: document.body.scrollHeight, viewportHeight: innerHeight }))
      item.responseOk = item.responses.some(response => response.status === 200) && !item.responses.some(response => response.status >= 400)
      item.rendered = item.responseOk && !item.frame.url.startsWith('chrome-error:') && /histogram|rating/i.test(item.frame.html)
      await page.locator('.letterboxd-rating').screenshot({ path: `${directory}/screenshots/${variant.name}.png` })
    } catch (error) { item.error = error.message }
    report.checks.push(item)
    console.log(JSON.stringify({ ...item, frame: item.frame && { ...item.frame, html: undefined } }))
    await page.close()
  }
} finally {
  await browser.close()
  fs.writeFileSync(`${directory}/letterboxd-live-verification.json`, JSON.stringify(report, null, 2))
}
