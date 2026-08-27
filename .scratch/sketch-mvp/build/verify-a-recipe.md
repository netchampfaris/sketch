# Verify a recipe boots

Two scripts, already used to prove the `blank` recipe boots clean. Use them.
Do not write your own harness.

## Step 1 — write the tree into a Prototype and get a signed URL

```
cd /home/faris/benches/sketch-bench/sites
/home/faris/benches/sketch-bench/env/bin/python \
  /home/faris/benches/sketch-bench/apps/sketch/.scratch/sketch-mvp/build/boot_recipe.py \
  rc-<slug> \
  /home/faris/benches/sketch-bench/apps/sketch/sketch/recipes/<slug>/src
```

It prints one signed Viewer URL, good for 600 seconds.

**The trap this script already handles:** Frappe overwrites `owner` with the
session user on insert. Set the session user first, or the Prototype lands on
`Administrator`, the `/u/orchmcp/...` lookup fails, and you get a 404 that looks
like a broken recipe but is a broken harness.

## Step 2 — boot it in a browser at 1280x800

```
cd /tmp/pw-runner
node /home/faris/benches/sketch-bench/apps/sketch/.scratch/sketch-mvp/build/boot_recipe.mjs "<url>"
```

It prints `window.__sketch`, `data-theme`, the first `h1`, failed requests and
console errors.

## The bar

A recipe is done when all four are true:

- `status` is `ok`
- `errors` is `[]`
- `consoleErrors` is `[]`
- failed requests is `[]`

**And real content is on screen.** A blank page that reports `ok` is still a
failure. Check the `h1` and take a screenshot.
