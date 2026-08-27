// The Runtime error classes, driven headless. `test_runtime_errors.py` reads
// the JSON this prints on stdout and makes the assertions.
//
// A port of runtime/test-errors.mjs. It carries its own good tree and its own
// three-line harness, so it never breaks when another agent edits the Runtime
// sample folder.
//
//   node runtime_errors.mjs <playwright entry> <viewer url>
import { pathToFileURL } from 'node:url'

const [, , playwrightEntry, viewerUrl] = process.argv
const { chromium } = await import(pathToFileURL(playwrightEntry).href)

// --------------------------------------------------------------- the harness
// The renderer's serialiser. `<` must be escaped, or the `</script>` in any
// SFC closes the JSON block early (trap 1).
function serialise(payload) {
	return JSON.stringify(payload)
		.replace(/</g, '\\u003c')
		.replace(/>/g, '\\u003e')
		.replace(/&/g, '\\u0026')
}

async function openViewer(context, files) {
	const data = serialise({
		files,
		name: 'd2t-runtime-errors',
		title: 'Runtime errors',
		slug: 'd2t-runtime-errors',
		pin: 'harness',
		is_public: false,
		is_owner: true,
		theme: 'light',
	})

	const page = await context.newPage()
	await page.route(viewerUrl, async (route) => {
		const response = await route.fetch()
		const body = await response.text()
		// One replace, and a function replacement, so `$&` in a source file is
		// not read as a back-reference.
		route.fulfill({
			status: 200,
			contentType: 'text/html; charset=utf-8',
			body: body.replace('SKETCH_DATA', () => data),
		})
	})
	await page.goto(viewerUrl, { waitUntil: 'commit' })
	await page.waitForFunction(() => window.__sketch, null, { timeout: 60000 })
	return page
}

// ----------------------------------------------------------------- good tree
const good = {
	'src/App.vue': `<script setup lang="ts">
import { Button } from 'frappe-ui'
</script>

<template>
  <div class="h-screen w-full bg-surface-base p-4 text-ink-gray-9">
    <Button label="Nothing" />
    <router-view />
  </div>
</template>
`,
	'src/router.ts': `import type { RouteRecordRaw } from 'vue-router'
import Home from './pages/Home.vue'
import About from './pages/About.vue'

const routes: RouteRecordRaw[] = [
  { path: '/', name: 'Home', component: Home },
  { path: '/about', name: 'About', component: About },
]

export default routes
`,
	'src/data.ts': `import { ref } from 'vue'

export interface Item {
  name: string
  title: string
}

export const items = ref<Item[]>([{ name: 'one', title: 'One' }])
`,
	'src/pages/Home.vue': `<script setup lang="ts">
import { items } from '../data'
</script>

<template>
  <h1 id="home">Home</h1>
  <p v-for="item in items" :key="item.name">{{ item.title }}</p>
</template>
`,
	'src/pages/About.vue': `<template>
  <h1 id="about">About</h1>
</template>
`,
}

// --------------------------------------------------------------- the cases
// `probe` runs after the case boots. It reports the one fact the case is about.
const cases = {
	'missing-end-tag': {
		files: { ...good, 'src/pages/About.vue': '<template>\n  <div class="p-4">\n    <span>oops\n  </div>\n</template>\n' },
	},
	'ts-syntax': { files: { ...good, 'src/data.ts': 'export const items = ref<Item[]>(\n' } },
	'bad-import': {
		files: { ...good, 'src/router.ts': good['src/router.ts'].replace('./pages/About.vue', './pages/Missing.vue') },
	},
	'bad-named-import': {
		files: {
			...good,
			'src/pages/About.vue': `<script setup lang="ts">\nimport { Badgee } from 'frappe-ui'\n</script>\n<template>\n  <Badgee />\n</template>\n`,
		},
	},
	'runtime-throw': {
		files: { ...good, 'src/pages/Home.vue': '<script setup>\nnull.boom()\n</script>\n<template><div/></template>\n' },
	},
	empty: { files: {} },
	'no-app': { files: { 'src/router.ts': good['src/router.ts'], 'src/pages/About.vue': good['src/pages/About.vue'] } },

	cycle: {
		files: {
			...good,
			'src/cycle-a.ts': "import { b } from './cycle-b'\nexport const a = 'A'\nexport function fromA() {\n  return a + b()\n}\n",
			'src/cycle-b.ts': "import { a } from './cycle-a'\nexport function b() {\n  return a\n}\n",
			'src/pages/About.vue': `<script setup lang="ts">\nimport { fromA } from '../cycle-a'\nconst cycle = fromA()\n</script>\n<template>\n  <p id="cycle">{{ cycle }}</p>\n</template>\n`,
		},
		probe: async (page) => {
			await page.evaluate(() => window.__sketchGoto('/about'))
			return { cycle: await page.textContent('#cycle') }
		},
	},

	vueuse: {
		files: {
			...good,
			'src/pages/About.vue': `<script setup lang="ts">\nimport { useCounter } from '@vueuse/core'\nconst { count, inc } = useCounter(1)\ninc(2)\n</script>\n<template>\n  <p id="vueuse">{{ count }}</p>\n</template>\n`,
		},
		probe: async (page) => {
			await page.evaluate(() => window.__sketchGoto('/about'))
			return { counter: await page.textContent('#vueuse') }
		},
	},

	css: {
		files: {
			...good,
			'src/style.css': '#css-probe { color: rgb(1, 2, 3); }\n',
			'src/pages/About.vue': `<script setup lang="ts">\nimport '../style.css'\n</script>\n<template>\n  <p id="css-probe">styled by an imported stylesheet</p>\n</template>\n`,
		},
		probe: async (page) => {
			await page.evaluate(() => window.__sketchGoto('/about'))
			return {
				colour: await page.evaluate(() => getComputedStyle(document.querySelector('#css-probe')).color),
				styleTags: await page.evaluate(() =>
					[...document.querySelectorAll('style[data-sketch-css]')].map((s) => s.dataset.sketchCss),
				),
			}
		},
	},

	// The escaping trap, end to end in a browser. Every SFC with a script block
	// ends with `</script>`, so a file that also holds one as text must survive.
	'closing-script-tag': {
		files: {
			...good,
			'src/pages/About.vue': `<script setup lang="ts">\nconst closing = '\\u003c/script\\u003e'\n</script>\n<template>\n  <p id="closing">{{ closing }}</p>\n</template>\n`,
		},
		probe: async (page) => {
			await page.evaluate(() => window.__sketchGoto('/about'))
			return { closing: await page.textContent('#closing') }
		},
	},
}

// ------------------------------------------------------------------- the run
const browser = await chromium.launch()
const context = await browser.newContext({ viewport: { width: 1280, height: 800 } })
const answers = {}

for (const [name, spec] of Object.entries(cases)) {
	let page = null
	try {
		page = await openViewer(context, spec.files)
		const report = await page.evaluate(() => window.__sketch)
		answers[name] = {
			status: report.status,
			errors: report.errors || [],
			warnings: report.warnings || [],
			consoleErrors: report.consoleErrors || [],
			routes: report.routes || [],
		}
		if (spec.probe) answers[name].probe = await spec.probe(page)
	} catch (e) {
		answers[name] = { harnessError: String(e?.message || e) }
	} finally {
		if (page) await page.close()
	}
}

await browser.close()
process.stdout.write(JSON.stringify(answers))
