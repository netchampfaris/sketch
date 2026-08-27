// Error classes the Viewer must report, checked against the built Runtime.
// Each case is the sample tree with one file changed.
import { chromium } from '/tmp/pw-runner/node_modules/playwright/index.mjs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { openViewer, readTree } from './harness.mjs'

const here = dirname(fileURLToPath(import.meta.url))
const good = readTree(join(here, 'sample-prototype'))

const cases = {
	'missing-end-tag': { ...good, 'src/pages/About.vue': '<template>\n  <div class="p-4">\n    <span>oops\n  </div>\n</template>\n' },
	'ts-syntax': { ...good, 'src/data.ts': 'export const issues = ref<Issue[]>(\n' },
	'bad-import': { ...good, 'src/router.ts': good['src/router.ts'].replace('./pages/About.vue', './pages/Missing.vue') },
	'bad-named-import': {
		...good,
		'src/pages/About.vue':
			'<script setup lang="ts">\nimport { Badgee } from \'frappe-ui\'\n</script>\n<template>\n  <Badgee />\n</template>\n',
	},
	'runtime-throw': { ...good, 'src/pages/Issues.vue': '<script setup>\nnull.boom()\n</script>\n<template><div/></template>\n' },

	// Change 5: no files at all, and a tree without src/App.vue.
	empty: {},
	'no-app': { 'src/router.ts': good['src/router.ts'], 'src/pages/About.vue': good['src/pages/About.vue'] },

	// Change 3: a two-file import cycle. A reads B at call time, B reads A at
	// call time, so both resolve.
	cycle: {
		...good,
		'src/cycle-a.ts': "import { b } from './cycle-b'\nexport const a = 'A'\nexport function fromA() {\n  return a + b()\n}\n",
		'src/cycle-b.ts': "import { a } from './cycle-a'\nexport function b() {\n  return a\n}\n",
		'src/pages/About.vue':
			'<script setup lang="ts">\nimport { fromA } from \'../cycle-a\'\nconst cycle = fromA()\n</script>\n<template>\n  <p id="cycle">{{ cycle }}</p>\n</template>\n',
	},

	// Change 7: the ninth specifier resolves, and only on demand.
	vueuse: {
		...good,
		'src/pages/About.vue':
			'<script setup lang="ts">\nimport { useCounter } from \'@vueuse/core\'\nconst { count, inc } = useCounter(1)\ninc(2)\n</script>\n<template>\n  <p id="vueuse">{{ count }}</p>\n</template>\n',
	},

	// Change 4: a .css import becomes a stylesheet.
	css: {
		...good,
		'src/style.css': '#css-probe { color: rgb(1, 2, 3); }\n',
		'src/pages/About.vue':
			'<script setup lang="ts">\nimport \'../style.css\'\n</script>\n<template>\n  <p id="css-probe">styled by an imported stylesheet</p>\n</template>\n',
	},
}

const browser = await chromium.launch()
const context = await browser.newContext({ viewport: { width: 1280, height: 800 } })
for (const [name, files] of Object.entries(cases)) {
	const page = await openViewer(context, files)
	const r = await page.evaluate(() => window.__sketch)
	console.log(`\n${name} -> ${r.status}`)
	for (const e of r.errors) console.log('   error:', JSON.stringify(e).slice(0, 220))
	for (const w of r.warnings) console.log('   warning:', JSON.stringify(w).slice(0, 220))

	if (name === 'cycle') {
		await page.evaluate(() => window.__sketchGoto('/about'))
		console.log('   cycle value:', await page.textContent('#cycle'))
	}
	if (name === 'vueuse') {
		await page.evaluate(() => window.__sketchGoto('/about'))
		console.log('   useCounter(1) after inc(2):', await page.textContent('#vueuse'))
	}
	if (name === 'css') {
		await page.evaluate(() => window.__sketchGoto('/about'))
		console.log('   injected colour:', await page.evaluate(() => getComputedStyle(document.querySelector('#css-probe')).color))
		console.log('   style tags:', await page.evaluate(() => [...document.querySelectorAll('style[data-sketch-css]')].map((s) => s.dataset.sketchCss)))
	}
	await page.close()
}
await browser.close()
