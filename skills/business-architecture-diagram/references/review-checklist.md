# Business Architecture Diagram Review Checklist

Use this checklist after each substantial edit. It mirrors the SKILL.md workflow: template
start, hard layout rules, mechanical pre-checks, then visual review.

## 0. Template and mechanical pre-checks

- Did the diagram start from `assets/svg-base.svg` and reuse its classes (no per-element inline styles)?
- `xmllint --noout diagram.svg` passes?
- `python3 scripts/check_text_overflow.py diagram.svg` reports OK (no overflow, no dangling `url(#id)`)?

## 1. Content

- Does each layer represent a clear business responsibility?
- Are labels phrased for the intended audience?
- Is the value statement still aligned with the diagram body?

## 2. Terminology

- Avoid mixing product interaction wording with management wording.
- Avoid mixing human roles, platform modules, and orchestration mechanisms in one naming pattern.
- Prefer one naming system per row.

Better executive wording examples:

- `人工介入` -> `人工审批与接管`
- `Skill / MCP` -> `能力市场 / 组件接入`
- `Trace / 成本 / CI/CD` -> `观测成本 / 发布管理`

## 3. Layout

- Hard rules hold: coordinates/spacing on the 4px grid; one accent color on at most 1-2 focal elements; vertical card spacing >= 40px; filtered elements >= 30px from the viewBox edge.
- Is every long label explicitly wrapped with `tspan` where needed?
- Are title bars, section captions, and bottom value statements visually separated?
- Is the side loop lighter than the main architecture body?

## 4. Arrows

- Source order is bands -> lines -> cards, so cards sit on top of line endpoints?
- Do arrows route through the corridors between cards, showing direction without crossing text or entering cards?
- Are repeated same-direction cross-layer arrows merged into one trunk line?
- Are explicit triangles cleaner than marker arrows in this file?

## 5. Versioning

- Preserve the prior version only when the user explicitly asks for a backup, comparison copy, or alternate方案.
- Keep PNG previews temporary unless the user explicitly wants a deliverable raster export.
