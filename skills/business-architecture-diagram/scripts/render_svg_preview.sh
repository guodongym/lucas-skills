#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: render_svg_preview.sh <input.svg> [output.png]" >&2
  exit 1
fi

input_svg="$1"
output_png="${2:-/tmp/$(basename "${input_svg%.svg}")_preview.png}"

if [[ ! -f "$input_svg" ]]; then
  echo "Input SVG not found: $input_svg" >&2
  exit 1
fi

chrome_bin=""
for candidate in \
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
do
  if [[ -x "$candidate" ]]; then
    chrome_bin="$candidate"
    break
  fi
done

if [[ -z "$chrome_bin" ]]; then
  echo "No supported headless browser found. Install Google Chrome or Microsoft Edge." >&2
  exit 1
fi

"$chrome_bin" \
  --headless \
  --disable-gpu \
  --hide-scrollbars \
  --window-size=1600,900 \
  --screenshot="$output_png" \
  "file://$input_svg"

echo "$output_png"
