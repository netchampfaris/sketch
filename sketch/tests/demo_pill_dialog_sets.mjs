// The owner's Viewer on a Prototype whose "Account style" set sits in a component used on /account and inside an
// app-wide dialog. `test_demo_pill_dialog_sets.py` writes the Prototype, reads the JSON this prints on stdout and makes
// the assertions.
//
//   node demo_pill_dialog_sets.mjs <playwright entry> <host> <port> <viewer path> <sid>
//
// On / with the dialog closed: what the Demo pill lists, what hovering its rows outlines, and a pick. Then the dialog
// opens on that pick, the pill is under its backdrop as before, and the row is still there once it closes. Then /reports,
// and /account with the dialog open over the page.
import { pathToFileURL } from 'node:url'

const [, , playwrightEntry, host, port, viewerPath, sid] = process.argv
const { chromium } = await import(pathToFileURL(playwrightEntry).href)

const ORIGIN = `http://${host}:${port}`
const BOOT_MS = 60000
// The frame looks behind closed dialogs a moment after the page settles.
const SETTLE_MS = 1200

const answer = {}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const browser = await chromium.launch({ args: [`--host-resolver-rules=MAP ${host} 127.0.0.1`] })
const context = await browser.newContext({ viewport: { width: 1280, height: 800 } })
await context.addCookies([{ name: 'sid', value: sid, url: ORIGIN }])
// The Demo pill's rows as the frame last reported them, also while the pill is under a dialog and cannot open.
await context.addInitScript(() => {
  if (window.top !== window) return
  window.addEventListener('message', (e) => {
    if (e.data?.type === 'model') window.__pillSets = (e.data.data?.sets ?? []).map((s) => s.label)
  })
})

try {
  const page = await context.newPage()
  const logs = []
  page.on('console', (m) => m.type() === 'error' && logs.push(m.text().slice(0, 300)))
  page.on('pageerror', (e) => logs.push(String(e).slice(0, 300)))

  const frameOf = async () => {
    const deadline = Date.now() + BOOT_MS
    while (Date.now() < deadline) {
      const f = page.frames().find((x) => x.url().includes('frame=1'))
      if (f) return f
      await sleep(250)
    }
    throw new Error('the shell never framed the Prototype')
  }
  const pill = page.locator('[data-pill="demo"] button').first()
  const card = page.locator('#sketch-demo-card')
  const rows = () => card.locator('.col-span-full > span:first-child').allInnerTexts()
  const openCard = async () => {
    if (!(await card.isVisible())) await pill.click()
    await card.waitFor({ state: 'visible', timeout: BOOT_MS })
    await sleep(300)
  }
  const closeCard = async () => {
    if (await card.isVisible()) await pill.click()
    await sleep(200)
  }
  const pick = async (set, option) => {
    await card.locator(`button[aria-label^="${set}:"]`).click()
    await page.getByRole('menuitem', { name: option }).click()
    await sleep(500)
  }
  // The page's own open dialog, never one of ours.
  const dialogOpen = (f) => f.evaluate(() => [...document.querySelectorAll('[role="dialog"][data-state="open"]')].some((d) => !d.closest('[data-sketch-ui]')))
  const dialogText = (f) => f.evaluate(() => [...document.querySelectorAll('[role="dialog"] .account-style')].filter((d) => !d.closest('[data-sketch-ui]')).map((d) => d.textContent)[0] ?? '')
  const outlined = () => page.locator('[data-sketch-ui="variants"].border-2').count()

  // 1. Home, the dialog closed.
  await page.goto(`${ORIGIN}${viewerPath}#/`, { waitUntil: 'load', timeout: BOOT_MS })
  const frame = await frameOf()
  await frame.getByText('Grid').waitFor({ timeout: BOOT_MS })
  await pill.waitFor({ timeout: BOOT_MS })
  await sleep(SETTLE_MS)
  await openCard()
  answer.homeRows = await rows()
  answer.homeDialogOpen = await dialogOpen(frame)
  await card.locator('.col-span-full', { hasText: 'Home layout' }).hover()
  await sleep(400)
  answer.outlineOnScreen = (await outlined()) > 0
  await card.locator('.col-span-full', { hasText: 'Account style' }).hover()
  await sleep(400)
  answer.outlineHidden = (await outlined()) > 0
  await pick('Account style', 'Detailed')
  answer.hashAfterPick = await frame.evaluate(() => location.hash)
  await closeCard()

  // The dialog opens on that pick.
  await frame.getByRole('button', { name: 'Account settings' }).click()
  await frame.locator('[role="dialog"] .account-style').waitFor({ timeout: BOOT_MS })
  await sleep(400)
  answer.dialogShows = await dialogText(frame)

  // With the dialog open the pill is under its backdrop, as before: tinted, inert, and a press on it is a press on the
  // backdrop, which closes the dialog. Once closed, the row is still listed, on the pick.
  const under = {}
  under.tint = (await page.locator('[data-pill="demo"] > div[aria-hidden="true"]').count()) > 0
  under.inert = await pill.evaluate((b) => b.inert || !!b.closest('[inert]'))
  await page.locator('[data-pill="demo"] > div[aria-hidden="true"]').click()
  await sleep(600)
  under.dialogOpenAfterPress = await dialogOpen(frame)
  await openCard()
  under.rows = await rows()
  under.current = await card.locator('button[aria-label^="Account style:"]').getAttribute('aria-label')
  await closeCard()
  answer.underDialog = under

  // A dialog mounted in one page: listed there.
  await frame.getByRole('link', { name: 'Reports' }).click()
  await frame.getByRole('button', { name: 'Filters' }).waitFor({ timeout: BOOT_MS })
  await sleep(SETTLE_MS)
  await openCard()
  answer.reportsRows = await rows()
  await closeCard()
  // The page takes its summary section away: its set is not behind a dialog, so its row goes.
  await frame.getByRole('button', { name: 'Hide summary' }).click()
  await sleep(SETTLE_MS)
  await openCard()
  answer.reportsRowsHidden = await rows()
  answer.reportsHashHidden = await frame.evaluate(() => location.hash)
  await closeCard()

  // 4. /account, with the dialog open over the page's own copy.
  await frame.getByRole('link', { name: 'Account page' }).click()
  await frame.getByRole('heading', { name: 'Account page' }).waitFor({ timeout: BOOT_MS })
  await sleep(SETTLE_MS)
  await frame.getByRole('button', { name: 'Account settings' }).click()
  await frame.locator('[role="dialog"] .account-style').waitFor({ timeout: BOOT_MS })
  await sleep(SETTLE_MS)
  const both = { rows: await page.evaluate(() => window.__pillSets) }
  // One pick drives both copies: close the dialog, pick, open it again.
  await frame.locator('[role="dialog"][data-state="open"]').press('Escape')
  await frame.locator('[role="dialog"][data-state="open"]').waitFor({ state: 'detached', timeout: BOOT_MS })
  await openCard()
  both.rowsClosed = await rows()
  await pick('Account style', 'Compact')
  await closeCard()
  await frame.getByRole('button', { name: 'Account settings' }).click()
  await frame.locator('[role="dialog"] .account-style').waitFor({ timeout: BOOT_MS })
  await sleep(400)
  both.shown = await frame.evaluate(() => [...document.querySelectorAll('.account-style')].filter((d) => !d.closest('[data-sketch-ui]')).map((d) => d.textContent))
  answer.accountBoth = both

  // Open page from a canvas tile is one pick too. Both copies are put on Tabs; the page's Compact tile, opened as a page,
  // puts both on Compact, the default, so the link names no option.
  await frame.locator('[role="dialog"][data-state="open"]').press('Escape')
  await frame.locator('[role="dialog"][data-state="open"]').waitFor({ state: 'detached', timeout: BOOT_MS })
  await sleep(SETTLE_MS)
  await openCard()
  await pick('Account style', 'Tabs')
  await card.getByRole('button', { name: 'Open canvas' }).click()
  await frame.waitForFunction(() => document.querySelectorAll('[data-tile-id] [inert]').length >= 3, null, { timeout: BOOT_MS })
  await sleep(SETTLE_MS)
  await frame.locator('[data-tile-id] [data-tile]').first().click()
  await frame.locator('[data-live]').waitFor({ state: 'attached', timeout: BOOT_MS })
  await frame.getByRole('button', { name: 'Actions for this variant' }).click()
  // The shell's tile menu takes no press that began as it opened.
  await page.getByRole('menuitem', { name: 'Open page' }).waitFor({ timeout: BOOT_MS })
  await sleep(500)
  await page.getByRole('menuitem', { name: 'Open page' }).click()
  await frame.locator('[data-sketch-ui="canvas"]').waitFor({ state: 'detached', timeout: BOOT_MS })
  await sleep(SETTLE_MS)
  const texts = () => frame.evaluate(() => [...document.querySelectorAll('.account-style')].filter((d) => !d.closest('[data-sketch-ui]')).map((d) => d.textContent))
  const opened = { page: await texts() }
  await frame.getByRole('button', { name: 'Account settings' }).click()
  await frame.locator('[role="dialog"] .account-style').waitFor({ timeout: BOOT_MS })
  await sleep(400)
  opened.shown = await texts()
  opened.hash = await frame.evaluate(() => location.hash)
  answer.openedPage = opened
  answer.errors = logs
} finally {
  await context.close()
  await browser.close()
}

process.stdout.write(JSON.stringify(answer))
