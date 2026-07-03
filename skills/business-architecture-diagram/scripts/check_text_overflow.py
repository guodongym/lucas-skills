#!/usr/bin/env python3
"""Heuristic pre-checks for hand-authored diagram SVGs.

Checks:
1. Text overflow: estimated text width (CJK ~= 1.0 em, Latin ~= 0.55 em) vs enclosing rect width.
2. Dangling url(#id) references (markers, gradients) with no matching element id.

Heuristic only: PNG preview remains the final visual judge.
"""

from __future__ import annotations

import re
import sys
import unicodedata
import xml.etree.ElementTree as ET

SVG_NS = "{http://www.w3.org/2000/svg}"
CJK_EM = 1.0
LATIN_EM = 0.55
PADDING = 16.0
DEFAULT_FONT_SIZE = 16.0


def parse_class_styles(root: ET.Element) -> dict[str, dict[str, str]]:
    styles: dict[str, dict[str, str]] = {}
    for style_el in root.iter(f"{SVG_NS}style"):
        css = style_el.text or ""
        for match in re.finditer(r"\.([\w-]+)\s*\{([^}]*)\}", css):
            cls, body = match.group(1), match.group(2)
            props = styles.setdefault(cls, {})
            for prop in body.split(";"):
                if ":" in prop:
                    key, value = prop.split(":", 1)
                    props[key.strip()] = value.strip()
    return styles


def font_size_of(el: ET.Element, styles: dict[str, dict[str, str]]) -> float:
    raw = el.get("font-size")
    if not raw:
        for cls in (el.get("class") or "").split():
            raw = styles.get(cls, {}).get("font-size")
            if raw:
                break
    if not raw:
        return DEFAULT_FONT_SIZE
    match = re.match(r"([\d.]+)", raw)
    return float(match.group(1)) if match else DEFAULT_FONT_SIZE


def anchor_of(el: ET.Element, styles: dict[str, dict[str, str]]) -> str:
    raw = el.get("text-anchor")
    if not raw:
        for cls in (el.get("class") or "").split():
            raw = styles.get(cls, {}).get("text-anchor")
            if raw:
                break
    return raw or "start"


def est_width(text: str, font_size: float) -> float:
    # A（ambiguous，如 — … ·）按全宽计：本 skill 以中文图为主，宁可高估宽度多报换行
    return sum(
        CJK_EM if unicodedata.east_asian_width(ch) in ("W", "F", "A") else LATIN_EM
        for ch in text
    ) * font_size


def text_lines(el: ET.Element) -> list[str]:
    tspans = list(el.iter(f"{SVG_NS}tspan"))
    if tspans:
        return [(t.text or "").strip() for t in tspans if (t.text or "").strip()]
    return [(el.text or "").strip()] if (el.text or "").strip() else []


def check(path: str) -> list[str]:
    tree = ET.parse(path)
    root = tree.getroot()
    styles = parse_class_styles(root)
    problems: list[str] = []

    rects = []
    for rect in root.iter(f"{SVG_NS}rect"):
        try:
            rects.append(
                (
                    float(rect.get("x", "0")),
                    float(rect.get("y", "0")),
                    float(rect.get("width", "0")),
                    float(rect.get("height", "0")),
                )
            )
        except ValueError:
            continue

    for text_el in root.iter(f"{SVG_NS}text"):
        try:
            tx = float(text_el.get("x", "0"))
            ty = float(text_el.get("y", "0"))
        except ValueError:
            continue
        size = font_size_of(text_el, styles)
        anchor = anchor_of(text_el, styles)
        enclosing = [
            (x, y, w, h)
            for (x, y, w, h) in rects
            if x <= tx <= x + w and y <= ty <= y + h
        ]
        if not enclosing:
            continue
        # 最小的包含矩形视为所属卡片
        x, y, w, h = min(enclosing, key=lambda r: r[2] * r[3])
        for line in text_lines(text_el):
            width = est_width(line, size)
            if anchor == "middle":
                fits = width / 2 <= min(tx - x, x + w - tx) - PADDING / 2
            elif anchor == "end":
                fits = width <= tx - x - PADDING
            else:
                fits = width <= x + w - tx - PADDING
            if not fits:
                problems.append(
                    f"OVERFLOW: '{line[:24]}' est {width:.0f}px exceeds card w={w:.0f} at ({tx:.0f},{ty:.0f})"
                )

    ids = {el.get("id") for el in root.iter() if el.get("id")}
    svg_text = ET.tostring(root, encoding="unicode")
    for ref in set(re.findall(r"url\(#([\w-]+)\)", svg_text)):
        if ref not in ids:
            problems.append(f"DANGLING REF: url(#{ref}) has no matching element id")

    return problems


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: check_text_overflow.py <file.svg>", file=sys.stderr)
        return 2
    try:
        problems = check(sys.argv[1])
    except (ET.ParseError, OSError) as e:
        print(f"error: cannot parse {sys.argv[1]}: {e}", file=sys.stderr)
        return 2
    for problem in problems:
        print(problem)
    if problems:
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
