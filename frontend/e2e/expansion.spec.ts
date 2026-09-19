import { test, expect } from '@playwright/test'
import { randomBytes } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve('..')
const shots = path.join(root, 'data/expansion/screenshots')
fs.mkdirSync(shots, { recursive: true })

test('homepage retains ranking inside approved movies and renders five new sections', async ({ page, request }) => {
  await page.goto('/')
  const response = await request.get('/api/v1/movies/?homepage=true&ordering=rating&page_size=6')
  expect(response.ok()).toBe(true)
  const data = await response.json()
  expect(data.results.every((movie: { is_homepage_eligible: boolean; vote_count: number }) => movie.is_homepage_eligible && movie.vote_count >= 200)).toBe(true)
  await expect(page.locator('.feature-content h1')).toHaveText(data.results[0].title)
  const firstRow = page.locator('#essentials .poster-link')
  await expect(firstRow).toHaveCount(6)
  expect(await firstRow.evaluateAll(items => items.map(item => item.getAttribute('href')))).toEqual(data.results.map((movie: { tmdb_id: number }) => '/films/' + movie.tmdb_id))
  for (const name of ['Drama', 'Horror', 'Black & White', 'Animation', 'International Cinema']) {
    const section = page.getByRole('region', { name, exact: true })
    await expect(section.locator('.film-card')).toHaveCount(6)
  }
  await page.getByRole('region', { name: 'Black & White', exact: true }).getByRole('link', { name: 'View all' }).click()
  await expect(page).toHaveURL(/theme=blackwhite/)
  await expect(page.locator('.film-card').first()).toBeVisible()
  await expect(page.getByText('Selected from our curated collection: Black & White.')).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: path.join(shots, 'curated-browse-mobile.png') })
})

test('optional half-star ratings and one editable public review work end to end', async ({ page, browser }) => {
  const username = 'phase6_browser_' + randomBytes(8).toString('hex')
  const password = 'Review-check-' + randomBytes(16).toString('hex')
  const first = 'The quiet pauses and measured framing stayed with me after the credits.'
  const edited = 'The measured framing rewards attention. Literal text: <script>window.reviewInjected=true</script>'
  try {
    await page.goto('/films/238')
    await expect(page.getByRole('region', { name: 'Film reviews' })).toBeVisible()
    await expect(page.getByRole('textbox', { name: /Your review/ })).toHaveCount(0)
    await page.goto('/register?next=/films/238')
    await page.getByLabel('Username', { exact: true }).fill(username)
    await page.getByLabel('Password', { exact: true }).fill(password)
    await page.getByRole('button', { name: 'Create account', exact: true }).click()
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('The Godfather')
    await page.getByRole('radio', { name: '4.5 out of 5 stars', exact: true }).check()
    await page.getByRole('button', { name: 'Save rating', exact: true }).click()
    await expect(page.getByRole('status').filter({ hasText: 'Your rating is saved.' })).toBeVisible()
    await expect(page.getByRole('textbox', { name: /Your review/ })).toHaveValue('')
    await page.getByRole('textbox', { name: /Your review/ }).fill(first)
    await page.getByRole('button', { name: 'Publish review', exact: true }).click()
    await expect(page.locator('.review-card').filter({ hasText: username })).toHaveCount(1)
    await expect(page.locator('.review-card').filter({ hasText: username })).toContainText('4.5/5')
    await page.getByRole('radio', { name: '4 out of 5 stars', exact: true }).check()
    await page.getByRole('textbox', { name: /Your review/ }).fill(edited)
    await page.getByRole('button', { name: 'Update review', exact: true }).click()
    await expect(page.locator('.review-card').filter({ hasText: username })).toHaveCount(1)
    await expect(page.locator('.review-card').filter({ hasText: username })).toContainText(edited)
    expect(await page.evaluate(() => 'reviewInjected' in window)).toBe(false)
    const guest = await browser.newContext()
    try {
      const guestPage = await guest.newPage()
      await guestPage.goto('http://127.0.0.1:5173/films/238')
      await expect(guestPage.locator('.review-card').filter({ hasText: username })).toContainText('4/5')
      await expect(guestPage.getByRole('textbox', { name: /Your review/ })).toHaveCount(0)
    } finally { await guest.close() }
    await page.setViewportSize({ width: 390, height: 844 })
    await page.getByRole('textbox', { name: /Your review/ }).scrollIntoViewIfNeeded()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: path.join(shots, 'optional-review-mobile.png') })
    await page.getByRole('button', { name: 'Delete review', exact: true }).click()
    await expect(page.getByRole('status').filter({ hasText: 'Review removed. Your star rating is kept.' })).toBeVisible()
    await expect(page.locator('.review-card').filter({ hasText: username })).toHaveCount(0)
    await page.goto('/collection?tab=ratings')
    await expect(page.getByText('Your rating: 4/5')).toBeVisible()
  } finally {
    const output = execFileSync(path.join(root, '.venv/Scripts/python.exe'), ['scripts/cleanup_phase6_test_account.py', username], { cwd: root, encoding: 'utf8', timeout: 60_000 })
    expect(output).toMatch(/Removed|No browser-test account/)
  }
})
