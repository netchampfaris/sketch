#!/bin/sh
# Adds a Runtime version: yarn runtime:add [version]
#
# Copies the newest version's inputs, sets frappe-ui to <version>, installs,
# and builds. The other build tools keep the versions the newest lockfile
# pins. Without a version, it takes the npm `latest` tag.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
VERSION=${1:-$(npm view frappe-ui dist-tags.latest)}
[ -n "$VERSION" ] || { echo "could not read frappe-ui's latest version from npm" >&2; exit 1; }
DIR=$HERE/versions/$VERSION
[ ! -e "$DIR" ] || { echo "$VERSION is already added: $DIR" >&2; exit 1; }
FROM=$(node "$HERE/versions.mjs" newest "$HERE/versions")

echo "adding $VERSION, from the inputs of $FROM"
mkdir -p "$DIR"
cp "$HERE/versions/$FROM/yarn.lock" "$DIR/yarn.lock"
node -e '
const fs = require("node:fs")
const [from, to, version] = process.argv.slice(1)
const pkg = JSON.parse(fs.readFileSync(from, "utf8"))
pkg.dependencies["frappe-ui"] = version
fs.writeFileSync(to, JSON.stringify(pkg, null, 2) + "\n")
' "$HERE/versions/$FROM/package.json" "$DIR/package.json" "$VERSION"
(cd "$DIR" && yarn install --non-interactive) || { rm -rf "$DIR"; exit 1; }

sh "$HERE/build.sh" "$VERSION"
echo "added $VERSION. Commit runtime/versions/$VERSION/."
