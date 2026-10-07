#!/bin/sh
# Builds one Runtime: sh build.sh <version> [--force]
#
# runtime/versions/<version>/ holds the build inputs: package.json and
# yarn.lock. This folder holds the shared source. The output goes to
# sketch/public/runtimes/<version>/, which is gitignored build output.
#
# The build is skipped when the output has a stamp from the same inputs.
# Set OUT to build into another folder, for example to check a rebuild
# before it replaces a live Runtime.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
VERSION=$1
[ -n "$VERSION" ] || { echo "usage: sh build.sh <version> [--force]" >&2; exit 1; }
INPUTS=$HERE/versions/$VERSION
[ -f "$INPUTS/yarn.lock" ] || { echo "no $INPUTS/yarn.lock. Add the version with: yarn runtime:add $VERSION" >&2; exit 1; }
RUNTIMES=$(cd "$HERE/../sketch/public" && pwd)/runtimes
OUT=${OUT:-$RUNTIMES/$VERSION}
mkdir -p "$(dirname "$OUT")"
OUT=$(cd "$(dirname "$OUT")" && pwd)/$(basename "$OUT")
BASE=/assets/sketch/runtimes/$VERSION

# The shared source that goes into every Runtime. A change to any of it, or
# to this version's lockfile, changes the stamp.
SOURCES="runtime-entry tailwind viewer fonts internals.css internals.tailwind.config.js
  vite.runtime.config.js make-lucide-map.mjs make-manifest.mjs build.sh package.json"
STAMP=$(cd "$HERE" && find $SOURCES "versions/$VERSION/package.json" "versions/$VERSION/yarn.lock" \
  -type f | LC_ALL=C sort | xargs sha256sum | sha256sum | cut -c1-16)
if [ "$2" != "--force" ] && [ "$(cat "$OUT/.build-stamp" 2>/dev/null)" = "$STAMP" ]; then
  echo "$VERSION: up to date, skipped"
  exit 0
fi
echo "$VERSION: building"

(cd "$INPUTS" && yarn install --frozen-lockfile --non-interactive --silent)

# Vite and esbuild resolve packages by walking up from the importing file.
# The work folder holds a copy of the shared source inside the version
# folder, so every import resolves to this version's node_modules. A fixed
# path keeps the output the same from one build to the next.
WORK=$INPUTS/.work
NM=$INPUTS/node_modules
ESBUILD=$NM/.bin/esbuild
STAGE=$(dirname "$OUT")/.$VERSION.building
trap 'rm -rf "$WORK" "$STAGE"' EXIT
rm -rf "$WORK"
mkdir -p "$WORK"
(cd "$HERE" && cp -R $SOURCES "$WORK/")
cd "$WORK"

# The renderer substitutes this line once per request (spec 6.2). build.sh
# stamps the empty slot, so the document is shared in source and versioned
# with the Pin at run time.
DATA_SLOT='<script id="sketch-data" type="application/json">SKETCH_DATA</script>'

rm -rf "$STAGE"
mkdir -p "$STAGE"

echo "[1/5] frappe-ui ESM assets"
RUNTIME_OUT="$STAGE" "$NM/.bin/vite" build -c "$WORK/vite.runtime.config.js" >/dev/null

echo "[2/5] vue + vue-router"
cp "$NM/vue/dist/vue.runtime.esm-browser.prod.js" "$STAGE/vue.js"
cp "$NM/vue-router/dist/vue-router.esm-browser.prod.js" "$STAGE/vue-router.js"
# vue-router's browser build imports "vue" by bare specifier; the import map
# resolves it, so both it and frappe-ui share one Vue instance. The dev build
# imports @vue/devtools-api, which no import map entry covers.

echo "[3/5] precompiled frappe-ui CSS (layer 1)"
"$NM/.bin/tailwindcss" -c "$WORK/internals.tailwind.config.js" \
  -i "$WORK/internals.css" -o "$STAGE/frappe-ui.css" --minify 2>/dev/null

# @vueuse/core is built on its own, not as a Vite entry. It ships as one
# module, so a shared entry hoists the whole barrel into the chunk frappe-ui
# loads eagerly. Standalone, it downloads only when a Prototype imports it.
"$ESBUILD" "$WORK/runtime-entry/vueuse.js" \
  --bundle --format=esm --platform=browser --minify --target=es2022 \
  --external:vue --outfile="$STAGE/vueuse.js" --log-level=warning

echo "[4/5] SFC compiler + Tailwind browser engine"
node "$WORK/make-lucide-map.mjs" "$NM/lucide-static/icons"
"$ESBUILD" "$WORK/runtime-entry/compiler.js" \
  --bundle --format=esm --platform=browser --minify --target=es2022 \
  --outfile="$STAGE/compiler.js" --log-level=warning
NM="$NM" ESBUILD="$ESBUILD" sh "$WORK/tailwind/build.sh" "$STAGE"

# Roman only. The italic face is 297 KB gzip, half the font payload, for text
# almost no Prototype sets in italic.
cp "$NM/frappe-ui/src/fonts/Inter/Inter.var.woff2" "$STAGE/Inter.var.woff2"

echo "[5/5] viewer + manifest"
# boot.js is cached by the browser and by Cloudflare. The document names it
# with this hash, so a changed file is a changed URL and reaches every client
# on the next page load.
BOOT_VERSION=$(md5sum "$WORK/viewer/boot.js" | cut -c1-8)
sed -e "s#RUNTIME#$BASE#g" -e "s#SKETCH_DATA_SLOT#$DATA_SLOT#" \
  -e "s#BOOT_VERSION#$BOOT_VERSION#" \
  "$WORK/viewer/viewer.html" > "$STAGE/viewer.html"
cp "$WORK/viewer/boot.js" "$STAGE/boot.js"
node "$WORK/make-manifest.mjs" "$VERSION" "$STAGE/manifest.json"
echo "$STAMP" > "$STAGE/.build-stamp"

# Swap the finished build in. A live Runtime is never half written. The
# dot-names are not valid Pins, so the server never lists them.
OLD=$(dirname "$OUT")/.$VERSION.old
rm -rf "$OLD"
if [ -e "$OUT" ]; then mv "$OUT" "$OLD"; fi
mv "$STAGE" "$OUT"
rm -rf "$OLD"
echo "done -> $OUT"
