# Business Architecture Diagram Review Checklist

Use this checklist after each substantial edit.

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

- Is every long label explicitly wrapped with `tspan` where needed?
- Are title bars, section captions, and bottom value statements visually separated?
- Is the side loop lighter than the main architecture body?

## 4. Arrows

- Do arrows show direction without crossing text?
- Are explicit triangles cleaner than marker arrows in this file?
- Do arrows stop outside cards rather than entering them?

## 5. Versioning

- Preserve the prior version only when the user explicitly asks for a backup, comparison copy, or alternate方案.
- Keep PNG previews temporary unless the user explicitly wants a deliverable raster export.
