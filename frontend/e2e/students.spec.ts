import { test, expect, type Page } from '@playwright/test'
import fs from 'node:fs'
const screenshots = '../data/phase8/screenshots'
fs.mkdirSync(screenshots, { recursive: true })

async function captureLoadedFrames(page: Page, filename: string) {
  // Full-page screenshots do not themselves trigger offscreen lazy images.
  const frames = page.locator('img[src*="/cinematography/frames/"]')
  await expect.poll(() => frames.evaluateAll(images => {
    // Related-film results can arrive after the primary study frames.
    images.forEach(image => { (image as HTMLImageElement).loading = 'eager' })
    return images.every(image => {
      const frame = image as HTMLImageElement
      return frame.complete && frame.naturalWidth > 0
    })
  }), { timeout: 60_000 }).toBe(true)
  await page.screenshot({ path: screenshots + '/' + filename, fullPage: true })
}

test('selected collection, study frames, masks and timestamp playback', async ({ page, request }) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  const response = await request.get('/api/v1/cinematography/films/')
  expect(response.ok()).toBe(true)
  expect((await response.json()).count).toBe(500)
  await page.goto('/students')
  await expect(page.getByRole('heading', { level: 1 })).toContainText('film students')
  await expect(page.locator('.student-film')).toHaveCount(20)
  await captureLoadedFrames(page, 'collection-desktop.png')
  await page.getByRole('searchbox', { name: 'Search student films' }).fill('Parasite')
  await page.getByRole('button', { name: 'Search', exact: true }).click()
  await expect(page.locator('.student-film')).toHaveCount(1)
  await page.locator('.student-film-caption').getByRole('link', { name: 'Parasite', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Parasite', exact: true })).toBeVisible()
  await expect(page.locator('.film-measurements')).toContainText('Color')
  await expect(page.locator('.study-card').first()).toBeVisible()
  const image = page.locator('.study-card img').first()
  await expect.poll(() => image.evaluate((i: HTMLImageElement) => i.naturalWidth)).toBeGreaterThan(0)
  const mask = page.getByRole('button', { name: 'Show text regions' }).first()
  if (await mask.count()) { await mask.click(); await expect(page.locator('.evidence-frame svg').first()).toBeVisible() }
  await page.getByRole('button', { name: /Watch at/ }).first().click()
  await expect(page.getByTitle('Parasite study video')).toHaveAttribute('src', /youtube-nocookie.*start=\d+/)
  await captureLoadedFrames(page, 'parasite-study.png')
  expect(errors).toEqual([])
})

test('comparison, interactive charts, quiz and anonymous contribution gate', async ({ page }) => {
  await page.goto('/students/compare?left=15&right=238')
  await expect(page.locator('.comparison-columns')).toContainText('Citizen Kane')
  await expect(page.locator('.comparison-columns')).toContainText('The Godfather')
  await expect(page.locator('.comparison-score')).toContainText('palette overlap')
  await captureLoadedFrames(page, 'comparison-desktop.png')
  await page.goto('/students/explore')
  await expect(page.locator('.scatter-chart svg circle').first()).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Color formats' })).toBeVisible()
  await page.goto('/students/quiz')
  await expect(page.locator('.quiz-options button')).toHaveCount(4)
  await page.locator('.quiz-options button').first().click()
  await expect(page.locator('.quiz-answer')).toBeVisible()
  await page.getByRole('button', { name: 'Next frame' }).click()
  await expect(page.locator('.quiz-answer')).toHaveCount(0)
  await page.goto('/students/contribute')
  await expect(page.getByRole('link', { name: 'Sign in to contribute' })).toBeVisible()
})

test('mobile study section has no horizontal page overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  for (const route of ['/students', '/students/compare?left=15&right=238', '/students/films/496243', '/students/explore']) {
    await page.goto(route)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    if (route === '/students') await expect(page.locator('.student-film')).toHaveCount(20)
    else if (route.includes('/compare')) await expect(page.locator('.comparison-score')).toBeVisible()
    else if (route.includes('/films/')) await expect(page.locator('.study-card').first()).toBeVisible()
    else await expect(page.locator('.scatter-chart svg circle').first()).toBeVisible()
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  }
  await page.screenshot({ path: screenshots + '/explorer-mobile.png', fullPage: true })
})

test('unavailable source state hides evidence and playback controls', async ({ page, request }) => {
  const response = await request.get('/api/v1/cinematography/films/83761/')
  expect(response.ok()).toBe(true)
  const film = { ...await response.json(), status: 'review', frames: [], study_cards: [], palette: [],
    metrics: {}, preview: null, playback_sources: [], reason: 'Source awaiting review in this browser test.' }
  // All 500 real sources may be ready; backend tests exercise the actual access gate.
  await page.route('**/api/v1/cinematography/films/83761/', route => route.fulfill({ json: film }))
  await page.goto('/students/films/83761')
  await expect(page.getByRole('heading', { name: film.title, exact: true })).toBeVisible()
  await expect(page.getByText(film.reason, { exact: true })).toBeVisible()
  await expect(page.locator('.study-card, .evidence-frame, .student-trailer iframe, .student-local-video')).toHaveCount(0)
})



test('reviewed Lady Vanishes featurette publishes only retained evidence with an honest scope', async ({ page, request }) => {
  const response = await request.get('/api/v1/cinematography/films/940/')
  expect(response.ok()).toBe(true)
  const film = await response.json()
  expect(film.status).toBe('ready')
  expect(film.scope).toContain('Promotional featurette')
  expect(film.quality.source_review.excluded_frame_indices.length).toBeGreaterThan(0)
  for (const frame of film.frames) expect(film.quality.source_review.excluded_frame_indices).not.toContain(frame.index)
  expect(film.source_url).toBe('https://www.youtube.com/watch?v=pTKfhyj2neg')
  await page.goto('/students/films/940')
  await expect(page.getByRole('heading', { name: 'The Lady Vanishes', exact: true })).toBeVisible()
  await expect(page.getByText(film.scope, { exact: true })).toBeVisible()
  await expect(page.locator('.evidence-frame')).toHaveCount(film.frames.length)
  await expect(page.locator('.student-film').first()).toBeVisible()
  await captureLoadedFrames(page, 'lady-vanishes-reviewed.png')
  await page.getByRole('button', { name: 'Open source video', exact: true }).click()
  await expect(page.getByTitle('The Lady Vanishes study video')).toHaveAttribute('src', /pTKfhyj2neg/)
})

test('owner supplied Life and Nothing More uses its supplied YouTube link without local playback', async ({ page, request }) => {
  const film = await (await request.get('/api/v1/cinematography/films/83761/')).json()
  expect(film.status).toBe('ready')
  expect(film.source_url).toBe('https://www.youtube.com/watch?v=66gdMLbiS8Y')
  expect(film.playback_sources[0].source_url).toBe(film.source_url)
  await page.goto('/students/films/83761')
  await expect(page.locator('.study-card').first()).toBeVisible()
  await page.getByRole('button', { name: /Watch at/ }).first().click()
  await expect(page.locator('.student-trailer iframe')).toHaveAttribute('src', /youtube-nocookie\.com\/embed\/66gdMLbiS8Y\?start=\d+/)
  await expect(page.locator('video')).toHaveCount(0)
})

test('combined sources preserve component timelines and shared trilogy scope', async ({ request }) => {
  for (const [mid, count] of [[34181, 4], [1405, 2], [8016, 2], [8429, 2], [307, 1]]) {
    const film = await (await request.get(`/api/v1/cinematography/films/${mid}/`)).json()
    expect(film.status).toBe('ready')
    expect(film.playback_sources).toHaveLength(count)
    expect(film.playback_sources[0].start).toBe(0)
    for (let i = 1; i < count; i++) {
      expect(film.playback_sources[i].start).toBeGreaterThan(film.playback_sources[i-1].start)
      expect(film.playback_sources[i-1].end).toBe(film.playback_sources[i].start)
    }
    if ([8016, 8429, 307].includes(mid)) expect(film.scope).toContain('Shared War Trilogy footage')
  }
})
