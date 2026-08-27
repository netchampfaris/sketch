#!/bin/sh
# Builds the browser Tailwind engine. Recipe from ticket 06, retargeted at
# sketch's own node_modules and frappe-ui 1.0.0-beta.55.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
NM=$HERE/../../frontend/node_modules
OUT=${1:-$HERE/dist}
mkdir -p "$OUT"
"${ESBUILD:-/tmp/sfc-bench/node_modules/esbuild/bin/esbuild}" "$HERE/entry.js" \
  --bundle --format=esm --platform=browser --minify --outfile="$OUT/tailwind.js" \
  --loader:.css=text --loader:.json=json \
  --alias:fs="$HERE/shims/fs.js" --alias:path="$HERE/shims/path.js" \
  --alias:url="$HERE/shims/url.js" --alias:crypto="$HERE/shims/crypto.js" \
  --alias:util="$HERE/shims/util.js" --alias:os="$HERE/shims/os.js" \
  --alias:fast-glob="$HERE/shims/fast-glob.js" --alias:micromatch="$HERE/shims/micromatch.js" \
  --alias:glob-parent="$HERE/shims/glob-parent.js" \
  --alias:TWLIB="$NM/tailwindcss/lib" --alias:FUI="$NM/frappe-ui" \
  --alias:tailwindcss="$NM/tailwindcss" --alias:postcss="$NM/postcss" \
  --alias:@tailwindcss/forms="$NM/@tailwindcss/forms" \
  --alias:@tailwindcss/typography="$NM/@tailwindcss/typography" \
  --alias:tailwindcss/plugin="$NM/tailwindcss/plugin.js" \
  --alias:tailwindcss/colors="$NM/tailwindcss/colors.js" \
  --alias:jiti="$HERE/shims/empty.js" --alias:sucrase="$HERE/shims/empty.js" \
  --alias:jiti/dist/babel.js="$HERE/shims/empty.js" \
  --define:process.env.DEBUG=undefined --define:process.env.NODE_ENV='"production"' \
  --define:process.env.JEST_WORKER_ID=undefined --define:process.env.TAILWIND_MODE=undefined \
  --define:process.env.TAILWIND_DISABLE_TOUCH=undefined --define:process.env.OXIDE=undefined \
  --define:process.env.TAILWIND_TOUCH_DIR=undefined --define:__dirname='"/tw"' \
  --inject:"$HERE/shims/process.js" --log-level=warning
