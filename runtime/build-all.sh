#!/bin/sh
# Builds every Runtime under runtime/versions/. build.sh skips a version
# whose output is already built from the same inputs, and never deletes
# another version's output.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
for dir in "$HERE"/versions/*/; do
  sh "$HERE/build.sh" "$(basename "$dir")"
done
