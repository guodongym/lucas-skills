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

# file:// URL 需要绝对路径，否则浏览器分支对相对路径调用生成坏 URL
input_svg="$(cd "$(dirname "$input_svg")" && pwd)/$(basename "$input_svg")"

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
  for candidate in google-chrome google-chrome-stable chromium chromium-browser microsoft-edge; do
    if command -v "$candidate" >/dev/null 2>&1; then
      chrome_bin="$(command -v "$candidate")"
      break
    fi
  done
fi

if [[ -z "$chrome_bin" ]] && command -v rsvg-convert >/dev/null 2>&1; then
  rsvg-convert -w 1600 -h 900 "$input_svg" -o "$output_png"
  echo "$output_png"
  exit 0
fi

if [[ -z "$chrome_bin" ]]; then
  echo "No renderer found. Install Google Chrome/Chromium/Edge or librsvg (rsvg-convert)." >&2
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
