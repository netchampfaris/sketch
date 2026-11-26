// The owner's Viewer on a Prototype whose "New prototype" set has a dialog as each option, closed on the page's home
// route, and whose Gallery page is also routed at /demo/new. `test_canvas_dialog_tiles.py` writes the Prototype, reads the
// JSON this prints on stdout and makes the assertions.
//
//   node canvas_dialog_tiles.mjs <playwright entry> <host> <port> <viewer path> <sid>
//
// Opens the canvas on the dialog set, reads what each tile shows and what the shell's Browse list holds, makes a tile
// live, then presses Escape. Then opens the canvas from /demo/new and from a page: link to it. Last, the page itself: the
// dialog its button opens is still a real modal one.
import { pathToFileURL } from 'node:url'

const [, , playwrightEntry, host, port, viewerPath, sid] = process.argv
const { chromium } = await import(pathToFileURL(playwrightEntry).href)

const ORIGIN = `http://${host}:${port}`
const BOOT_MS = 60000
// The live tile follows its set from the second frame after it mounts.
const SETTLE_MS = 1000

const answer = {}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const browser = await chromium.launch({ args: [`--host-resolver-rules=MAP ${host} 127.0.0.1`] })
const context = await browser.newContext({ viewport: { width: 1280, height: 800 } })
await context.addCookies([{ name: 'sid', value: sid, url: ORIGIN }])
// Every time focus lands in a canvas tile or in a frame drawing one, in every document of the page.
await context.addInitScript(() => {
  window.__focusedInTiles = 0
  document.addEventListener('focusin', (e) => {
    if (e.target?.closest?.('[data-tile-id], [data-sketch-ui="canvas-frame"]')) window.__focusedInTiles++
  }, true)
})

// What the frame's page says about dialogs and the real page while the canvas is open: dialogs outside the canvas, and
// what a modal dialog does to the page: locks its scroll (reka marks that with --scrollbar-width on the root), blocks its
// pointer, hides the rest from assistive tech.
const pageState = () => {
  const outside = [...document.querySelectorAll('[role="dialog"]')].filter((d) => !d.closest('[data-tile-id]') && d.getAttribute('data-sketch-ui') !== 'canvas')
  const canvas = document.querySelector('[data-sketch-ui="canvas"]')
  const hidden = []
  for (let n = canvas; n && n !== document.documentElement; n = n.parentElement) if (n.getAttribute('aria-hidden') === 'true') hidden.push(n.tagName)
  const active = document.activeElement
  return {
    dialogsOutside: outside.length,
    bodyPointer: getComputedStyle(document.body).pointerEvents,
    scrollLocked: document.documentElement.style.getPropertyValue('--scrollbar-width') !== '',
    canvasHidden: hidden,
    focusInTile: !!active?.closest?.('[data-tile-id]'),
    focusInFrame: !!active?.closest?.('[data-live]'),
    focusedInTiles: window.__focusedInTiles,
  }
}

// Each tile of the open view: its size on the canvas, whether it drops the frame, and its dialog panel.
const tiles = () =>
  [...document.querySelectorAll('[data-tile-id]')].map((t) => {
    const panel = t.querySelector('[role="dialog"]')
    const vis = (el) => !!el?.checkVisibility({ visibilityProperty: true })
    return {
      id: t.dataset.tileId,
      w: parseFloat(t.style.width),
      h: parseFloat(t.style.height),
      card: t.querySelector('[data-tile]')?.hasAttribute('data-tile-card') ?? false,
      live: !!t.querySelector('[data-live]'),
      panel: !!panel,
      panelVisible: vis(panel),
      panelW: panel?.offsetWidth ?? 0,
      panelH: panel?.offsetHeight ?? 0,
      panelText: panel?.innerText.slice(0, 200) ?? '',
      pageVisible: vis(t.querySelector('h1')),
      backdropVisible: vis(t.querySelector('.dialog-overlay')),
    }
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
  const open = async (hash, drawn) => {
    await page.goto(`${ORIGIN}${viewerPath}#${hash}`, { waitUntil: 'load', timeout: BOOT_MS })
    const frame = await frameOf()
    const why = async (e) => {
      const seen = await frame.evaluate(() => ({ hash: location.hash, text: document.body.innerText.slice(0, 1500) })).catch(() => null)
      throw new Error(`${e.message}\nthe frame: ${JSON.stringify(seen)}\nerrors: ${JSON.stringify(logs.slice(0, 20))}`)
    }
    await frame.waitForFunction((n) => document.querySelectorAll('[data-tile-id] [inert]').length >= n, drawn, { timeout: BOOT_MS }).catch(why)
    await sleep(SETTLE_MS)
    return { frame, why }
  }

  // 1. The dialog set, from the home route, where the dialog is closed.
  const { frame, why } = await open('/?canvas=set:gallery/new-prototype', 3)
  answer.hash = await frame.evaluate(() => location.hash)
  answer.tiles = await frame.evaluate(tiles)
  answer.drawnState = await frame.evaluate(pageState)
  // The shell's Browse list: one row per set and per page with states.
  answer.browse = await page.locator('[data-panel-row]').allInnerTexts()

  // 2. One tile made live.
  await frame.locator('[data-tile-id] [data-tile]').first().click()
  await frame.locator('[data-live]').waitFor({ state: 'attached', timeout: BOOT_MS }).catch(why)
  await sleep(SETTLE_MS)
  answer.liveTiles = await frame.evaluate(tiles)
  answer.liveState = await frame.evaluate(pageState)
  // Then each tile in turn, and back: every switch lifts the new live tile's dialog out of its page, and none takes focus.
  answer.switches = []
  // On every frame, just before paint (a ResizeObserver callback runs after rAF and layout): a live frame that paints
  // before it is lifted to its set (the whole page flashes), a tile that paints nothing, and a snapshot that is rebuilt
  // (its opening animations replay as the tile is handed back). With the CPU slowed, so a slow frame shows.
  await frame.evaluate(() => {
    const seen = (window.__paint = { frames: 0, unlifted: 0, blank: 0, rebuilt: 0 })
    const ids = new WeakMap()
    const last = {}
    let n = 0
    const vis = (el) => !!el && el.checkVisibility({ visibilityProperty: true, opacityProperty: true })
    const paints = (d) => !!d && (d.hasAttribute('data-sketch-lift') ? [...d.querySelectorAll('[data-sketch-lift-show]')].some(vis) : vis(d))
    const probe = document.body.appendChild(document.createElement('div'))
    probe.style.cssText = 'position:fixed;left:0;top:0;height:1px;pointer-events:none'
    new ResizeObserver(() => {
      seen.frames++
      document.querySelectorAll('[data-tile-id]').forEach((t, i) => {
        const live = t.querySelector('[data-live] [data-tile-drawing]')
        const snap = t.querySelector('[inert][data-tile-drawing]')
        if (live && vis(live) && !live.hasAttribute('data-sketch-lift')) seen.unlifted++
        if (!paints(live) && !paints(snap)) seen.blank++
        if (snap) {
          if (!ids.has(snap)) ids.set(snap, ++n)
          if (last[i] && last[i] !== ids.get(snap)) seen.rebuilt++
          last[i] = ids.get(snap)
        }
      })
    }).observe(probe)
    const tick = () => {
      probe.style.width = (seen.frames % 2) + 1 + 'px'
      requestAnimationFrame(tick)
    }
    requestAnimationFrame(tick)
  })
  const cdp = await context.newCDPSession(page)
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 })
  for (const i of [1, 2, 1, 2, 0]) {
    await frame.locator('[data-tile-id] [data-tile]').nth(i).click()
    await sleep(SETTLE_MS)
    answer.switches.push(await frame.evaluate((i) => {
      const live = document.querySelector('[data-live]')
      const vis = (el) => !!el?.checkVisibility({ visibilityProperty: true })
      return {
        tile: i,
        live: live?.closest('[data-tile-id]') === document.querySelectorAll('[data-tile-id]')[i],
        lifted: !!live?.querySelector('[data-tile-drawing]')?.hasAttribute('data-sketch-lift'),
        panelVisible: vis(live?.querySelector('[role="dialog"]')),
        pageVisible: vis(live?.querySelector('h1')),
        focusInFrame: !!document.activeElement?.closest('[data-live]'),
      }
    }, i))
  }
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 })
  answer.paint = await frame.evaluate(() => window.__paint)
  // Escape reaches the canvas, which closes the live tile: the tile's dialog does not take it.
  await page.keyboard.press('Escape')
  await sleep(300)
  answer.liveAfterEscape = (await frame.locator('[data-live]').count()) > 0
  answer.hashAfterEscape = await frame.evaluate(() => location.hash)

  // 3. The same set, from the route that opens the dialog as the page mounts, and the page's states from a link to it.
  const fromDemo = await open('/demo/new?canvas=set:gallery/new-prototype', 3)
  answer.demoTiles = await fromDemo.frame.evaluate(tiles)
  answer.demoBrowse = await page.locator('[data-panel-row]').allInnerTexts()
  const pageLink = await open('/demo/new?canvas=page:/demo/new', 2)
  answer.pageLinkHash = await pageLink.frame.evaluate(() => location.hash)
  answer.pageLinkTiles = await pageLink.frame.evaluate(tiles)

  // 4. The page with no canvas: its button opens the dialog as a real, modal one.
  await page.goto(`${ORIGIN}${viewerPath}#/`, { waitUntil: 'load', timeout: BOOT_MS })
  const plain = await frameOf()
  await plain.getByRole('button', { name: 'New prototype' }).click()
  await plain.locator('[role="dialog"]').waitFor({ state: 'visible', timeout: BOOT_MS })
  await sleep(300)
  answer.pageDialog = await plain.evaluate(() => {
    const d = document.querySelector('[role="dialog"]')
    return { inBody: d?.closest('[data-tile-id]') === null, state: d?.getAttribute('data-state'), bodyPointer: getComputedStyle(document.body).pointerEvents }
  })
  answer.errors = logs
} finally {
  await context.close()
  await browser.close()
}

process.stdout.write(JSON.stringify(answer))
