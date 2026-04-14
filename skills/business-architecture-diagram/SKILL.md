---
name: business-architecture-diagram
description: Create and iteratively refine executive-style business architecture diagrams as editable SVG assets, with optional PNG previews for review. Use when Codex needs to turn business notes, platform integration ideas, operating models, layered responsibilities, or management-facing architecture summaries into a clean diagram, or when the user asks in Chinese for 业务架构图, 架构图, 分层架构图, 汇报架构图, 平台融合图, SVG 架构图, 生成图片, 优化图片, 调整布局, 调整换行, 调整箭头, 润色文案, or 优化现有 SVG/PNG 架构图.
---

# Business Architecture Diagram

## Overview

Create leadership-friendly business architecture diagrams as hand-authored SVG files first, then iterate on wording and layout until the diagram is presentation-ready. Use PNG only for preview and review unless the user explicitly asks for a final raster export.

## Workflow

### 1. Normalize the content before drawing

Extract the diagram into a small set of consistent parts:

- audience: leadership, product, or technical review
- layers or bands: management, execution, infrastructure, or equivalent
- nodes within each layer
- key flows and arrows
- loop or closed-cycle elements
- bottom-line value proposition

Before drawing, unify naming style inside each layer. Avoid mixing role names, platform names, interaction verbs, and HR language in the same row unless that is intentional.

For leadership-facing diagrams:

- prefer 3 layers when possible
- keep each layer to 3-6 nodes
- prefer business language over implementation jargon
- convert interaction-heavy wording into mechanism wording

Examples:

- `OpenClaw + 人` -> `OpenClaw 与人工`
- `@数字员工即触发` -> `消息触发执行`
- `人工员工协同` -> `人工审批与接管`
- `K8s Pod 生命周期托管` -> `运行实例生命周期托管`

If the user wants a final deliverable rather than syntax, default to direct SVG instead of Mermaid.

### 2. Handle versioning only when requested

Do not default to backups or copied variants.

Create backup files or alternate versions only when the user explicitly asks to:

- preserve the current version
- create a backup
- copy the current diagram first
- compare multiple options

If the user does not ask for version preservation, edit the current SVG in place.

When the user says not to keep exporting PNG, continue editing only the SVG source and use preview PNGs only for validation.

### 3. Build the SVG directly

Use a presentation-oriented canvas by default:

- `1600 x 900` for slides
- rounded containers and cards
- restrained gradients and soft shadows
- explicit arrows and triangles when precise placement matters
- `tspan` line breaks for any text that risks overflow

Prefer this structure:

1. title bar
2. small English sublabel if it adds credibility and does not distract
3. main layered architecture area
4. side loop or operating cycle only if it matters to the story
5. bottom value bar

Keep the SVG editable:

- use real text nodes, not outlines
- keep styles centralized in `<style>`
- reuse classes for card titles, captions, loop labels, and value statements

### 4. Iterate in this order

When reviewing an existing diagram, inspect in this sequence:

1. content correctness
2. terminology consistency
3. text overflow and line wrapping
4. arrow logic and placement
5. alignment and spacing
6. visual weight and hierarchy

Specific rules:

- fix incorrect business wording before polishing visuals
- if text touches a card edge, add line breaks first, then increase card height if needed
- keep the right-side loop visually lighter than the main architecture
- make bottom value statements short and conclusion-oriented
- right-align subtitles in title bars if they visually compete with the main title

### 5. Validate both structure and visuals

Always run XML validation after edits:

```bash
xmllint --noout diagram.svg
```

If visual verification matters, render a temporary PNG preview and inspect:

```bash
scripts/render_svg_preview.sh diagram.svg
```

Review the preview for:

- cropped bottom content
- text outside rounded cards
- arrows colliding with labels or cards
- inconsistent card heights
- overly strong accent colors drawing attention away from the main structure

## Working Patterns

### Leadership-report style

Use this mode when the user says `领导汇报风`, `偏 PPT`, `简洁正式`, `汇报用`, `老板看`, `管理层看`, or asks for a board/executive architecture slide.

Optimize for:

- short labels
- minimal technical jargon
- stable hierarchy
- one clear takeaway

Recommended naming patterns:

- layer labels: `管理层`, `执行层`, `基础设施层`
- execution nodes: `任务助理`, `任务编排中枢`, `工具支持`, `人工审批与接管`
- loop labels: `任务下发`, `协同执行`, `知识沉淀`, `反馈优化`

### Technical-working style

Use this mode when the user wants architecture review, implementation discussion, technical decomposition, or a more engineering-heavy diagram.

Allow:

- platform component names
- technical labels such as `MCP`, `CI/CD`, `模型调度`
- denser annotations

Even in this mode, avoid unnecessary jargon if the same point can be made in clearer business language.

## Resources

### scripts/

- `scripts/render_svg_preview.sh`: render a temporary PNG preview from an SVG for visual review

### references/

- `references/review-checklist.md`: quick checklist for terminology, layout, arrows, and executive readability
