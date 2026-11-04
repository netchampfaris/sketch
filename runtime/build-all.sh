#!/bin/sh
# Builds every Runtime under runtime/versions/. build.sh skips a version
# whose output is already built from the same inputs, and never deletes
# another version's output.
#
# Then it removes the output of a version that is no longer in versions/,
# so a retired Runtime stops being served and listed as a Pin. Only the
# direct child folders of sketch/public/runtimes/ whose name is a Pin go:
# a dot-name (a build in progress, `.<version>.building`) and a symlink are
# never touched.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
for dir in "$HERE"/versions/*/; do
  sh "$HERE/build.sh" "$(basename "$dir")"
done

RUNTIMES=$HERE/../sketch/public/runtimes
[ -d "$RUNTIMES" ] || exit 0
RUNTIMES=$(cd "$RUNTIMES" && pwd)
for out in "$RUNTIMES"/*; do
  name=$(basename "$out")
  case "$name" in [A-Za-z0-9]*) ;; *) continue ;; esac
  [ -d "$out" ] && [ ! -L "$out" ] || continue
  [ -d "$HERE/versions/$name" ] && continue
  echo "$name: no longer in runtime/versions, removing its output"
  rm -rf "$RUNTIMES/$name"
done
