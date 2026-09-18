---
name: pixel-art-to-beads
description: "Generate or read pixel art and deliver four MARD bead charts: uncompressed original/mirror and board-fitted original/mirror. Support outline-preserving 52-cell compression, AI refinement and accurate counts. Use for 拼豆图纸、像素画转拼豆、52格压缩. Uses project tools/beads; no other skill or Lumina required."
---

# Pixel Art to Beads

The default final delivery is exactly four primary PNGs: **01_未压缩.png**, **02_未压缩_镜像.png**, **03_压缩.png**, **04_压缩_镜像.png**. Use the four-chart workflow in [bead-export.md](references/bead-export.md). Mirror each cell matrix horizontally, then render upright labels and coordinates. Each mirror pair shares the bead count for one physical work. Respect an explicit request for fewer variants or algorithm-only compression.

Keep the chart presentation concise: the main title is only the work's name; the mirrored chart adds “镜像版”. Do not print “正常版” on the chart. Omit explanatory captions and disclaimers such as “原始方向”, “一格一颗豆”, “色值为屏幕近似值”, “空格不放豆” and “非实物比例”. Keep the palette name, grid coordinates and material counts. Preserve provenance and technical limitations in project metadata and internal references, not chart decoration.

## Scope and independence

This directory contains instructions, prompts, style assets and palette data. Executable implementation lives in the project's `tools/beads/`, following the same rule/tool separation as the other skills. Locate the project by `tools/beads/run_workflow.py` and `skills/codex/pixel-art-to-beads/`; do not assume the installed skill directory is the project root. Do not invoke or read another skill. No Lumina, 3MF or printer profile is needed. See [runtime.md](references/runtime.md) to resolve tool paths, the Python runtime and fonts.

## Select the route

- **New artwork:** text, subject photo, character reference or requested creative edit -> generation, lightweight inspection, Perfect Pixel, final visual review, bead mapping.
- **Existing logical PNG:** one actual pixel per intended bead, including final grids from previous work -> skip generation and grid detection; enter the four-chart workflow. Do not mistake an enlarged preview for this file.
- **Enlarged pixel art:** recover its logical grid with the preparation tool, inspect, then map.
- **Saved pattern JSON:** re-render without image generation, grid detection or recoloring.
- **Fit a bead board / compress pixel dimensions:** read [compression.md](references/compression.md). Start from the untouched accepted logical source, not a previously repaired candidate. The user's usual board is 52×52; use that target when they request single-board fitting without another size. The selected workflow is algorithmic sizing followed by AI refinement and automatic Perfect Pixel checks. Preserve black exterior outlines without changing the global palette or interior facial colors. An explicit algorithm-only request skips AI.
- A photograph is a subject reference for new pixel art. A chart screenshot with printed codes/watermarks is a layout reference, not clean pixel input. Screenshot/OCR reconstruction is outside this version; request the clean pixel source if necessary.

Keep the user's provided original unchanged. A request to reuse artwork does not authorize redesign. Preserve explicit size, background, pose and palette choices. Missing routine preferences use the defaults below rather than an approval gate.

## Stage 1: Generate only if needed

Read [generation-prompt.md](references/generation-prompt.md), inspect authorized references and record `00_subject_brief.md` in a fresh run directory. Named recognizable characters use first-party research for canonical details. Generate a pixel source using the fenced prompt and save `01_source.png`.

Keep generation context separate: do not put color-card codes, matching metrics, bead counts, PDF typography or downstream error logs in the image prompt. Attach actual image references through the image tool. Do not ask the image model to draw the numbered bead chart.

Inspect that the subject and framing are present. Raw gradients, antialiasing, partial alpha or imperfect block edges go through refinement before final judgment. For a wrong subject or missing major content, retry from the original inputs, at most twice for the same failure. Do not attach a rejected generated result as a new reference. Preserve failures; do not claim an unaccepted candidate is finished.

## Stage 2: Prepare and review the logical grid

Once an image exists, read [pixel-refinement.md](references/pixel-refinement.md). Run the project's `tools/beads/prepare_source.py` on raw/enlarged pixel sources. Known final logical grids bypass this step unless explicit background preparation is needed.

Inspect the resulting preview for identity, silhouette, white subject details, intentional holes and background correctness. Default to preserving the input background; new isolated subjects prefer genuine transparent alpha. Never globally erase white or silently manufacture a fixed 50×50 grid. Grid detection failure needs source review, not a forced density pass.

After logical-grid acceptance, branch from the same original into an uncompressed pair and a board-fitted pair. Trim empty outer rows and columns from both uncompressed charts so the chart grid hugs the occupied bounding box. Preserve every occupied cell and internal empty cell without resampling; report the cropped dimensions, not the padded source canvas. The fitted pair defaults to 52×52, with algorithmic proportional sizing, outline protection, optional AI refinement and automatic grid checks. Record algorithmic resizing separately from AI changes. Use the reusable workflow instead of per-image coordinate edits. Do not add an outline to unoutlined art unless requested.

## Stage 3: Match colors and export

Read [bead-export.md](references/bead-export.md). Use `tools/beads/run_workflow.py prepare` on the accepted logical PNG, read [compression.md](references/compression.md) for the one AI refinement pass, then `run_workflow.py finish` to publish all four charts. The default is the bundled MARD 221 community palette. For a supplied palette, follow [palette-format.md](references/palette-format.md).

Defaults: tightly crop only transparent outer padding in the uncompressed pair; fit the compressed pair to 52×52 without stretching; transparent cells are empty; opaque white is a bead; no dithering; no fixed color cap; every 5 cells has a major line. PDFs, CSVs, previews and JSON remain in `work/`; only the four primary PNGs go in `delivery/`. If the user asks for a full background, select an explicit valid background code and preserve meaningful subject holes as requested.

Preserve the pre-mapping source and render a nearest-neighbor preview of the mapped result. Check important outlines, eyes, skin and accessories for unwanted color merges. If a cap damages recognition, adjust allowed/locked colors or explain the tradeoff; do not repaint the source silently. Disconnected occupied components are listed in JSON; visually review and disclose detached pieces, without automatically drawing connecting beads.

## Stage 4: Focused acceptance and delivery

Inspect both mirror pairs at full view and a representative label crop. Check counts, mirrored positions, upright text, cropped uncompressed dimensions, fitted dimensions, outer outline and facial readability. If delivering an optional PDF, inspect its rendering too. The workflow reports `four_charts_ready_for_review`; only set `manifest.json` status to `accepted` after visual checks. Record concise checks in `review.json`. Do not rerun unrelated project tests.

Show a compact contact sheet if helpful and link the four files in `delivery/`. Give dimensions, color count and bead count for each size. Retain original/AI sources, PDFs, material lists and editable JSON internally; do not present these as extra primary deliverables unless requested. A run with a missing pair is incomplete.
