#!/bin/sh
# One command. Builds the Runtime into sketch/public/runtimes/<version>/.
# The output is gitignored build output. This folder is the source.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
VERSION=1.0.0-beta.55
OUT=$HERE/../sketch/public/runtimes/$VERSION
NM=$HERE/../frontend/node_modules
BASE=/assets/sketch/runtimes/$VERSION

# The renderer substitutes this line once per request (spec 6.2). build.sh
# stamps the empty slot, so the document is shared in source and versioned
# with the Pin at run time.
DATA_SLOT='<script id="sketch-data" type="application/json">SKETCH_DATA</script>'

# Vite and esbuild resolve packages by walking up from their own directory,
# so this folder needs the frontend's node_modules beside it.
[ -e "$HERE/node_modules" ] || ln -s ../frontend/node_modules "$HERE/node_modules"

# esbuild is not a frontend dependency: Vite 8 ships rolldown instead.
ESBUILD=$NM/.bin/esbuild
[ -x "$ESBUILD" ] || ESBUILD=/tmp/sfc-bench/node_modules/esbuild/bin/esbuild
if [ ! -x "$ESBUILD" ]; then
  echo "esbuild not found. Install it, or set ESBUILD." >&2
  exit 1
fi

rm -rf "$OUT"
mkdir -p "$OUT"

echo "[1/5] frappe-ui ESM assets"
"$NM/.bin/vite" build -c "$HERE/vite.runtime.config.js" >/dev/null

echo "[2/5] vue + vue-router"
cp "$NM/vue/dist/vue.runtime.esm-browser.prod.js" "$OUT/vue.js"
cp "$NM/vue-router/dist/vue-router.esm-browser.prod.js" "$OUT/vue-router.js"
# vue-router's browser build imports "vue" by bare specifier; the import map
# resolves it, so both it and frappe-ui share one Vue instance. The dev build
# imports @vue/devtools-api, which no import map entry covers.

echo "[3/5] precompiled frappe-ui CSS (layer 1)"
"$NM/.bin/tailwindcss" -c "$HERE/internals.tailwind.config.js" \
  -i "$HERE/internals.css" -o "$OUT/frappe-ui.css" --minify 2>/dev/null

# @vueuse/core is built on its own, not as a Vite entry. It ships as one
# module, so a shared entry hoists the whole barrel into the chunk frappe-ui
# loads eagerly. Standalone, it downloads only when a Prototype imports it.
"$ESBUILD" "$HERE/runtime-entry/vueuse.js" \
  --bundle --format=esm --platform=browser --minify --target=es2022 \
  --external:vue --outfile="$OUT/vueuse.js" --log-level=warning

echo "[4/5] SFC compiler + Tailwind browser engine"
node "$HERE/make-lucide-map.mjs"
"$ESBUILD" "$HERE/runtime-entry/compiler.js" \
  --bundle --format=esm --platform=browser --minify --target=es2022 \
  --outfile="$OUT/compiler.js" --log-level=warning
ESBUILD="$ESBUILD" sh "$HERE/tailwind/build.sh" "$OUT"

# Roman only. The italic face is 297 KB gzip, half the font payload, for text
# almost no Prototype sets in italic.
cp "$NM/frappe-ui/src/fonts/Inter/Inter.var.woff2" "$OUT/Inter.var.woff2"

echo "[5/5] viewer + manifest"
sed -e "s#RUNTIME#$BASE#g" -e "s#SKETCH_DATA_SLOT#$DATA_SLOT#" \
  "$HERE/viewer/viewer.html" > "$OUT/viewer.html"
cp "$HERE/viewer/boot.js" "$OUT/boot.js"
node "$HERE/make-manifest.mjs" "$VERSION" "$OUT/manifest.json"

echo "done -> $OUT"
