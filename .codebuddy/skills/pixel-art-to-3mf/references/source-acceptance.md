# Stage 2 — Source Acceptance

Do not read this file until `01_source.png` exists. These rules are diagnostics for the completed source and are never image-generation prompt content.

## Generated-source gate

Inspect the completed image before accepting it:

- Require generated sources to be fully opaque with a uniform pure-white background. Any transparent or partially transparent generated pixel is a hard failure and requires a fresh generation. This generated-source rule does not reject a user-provided transparent PNG submitted for direct conversion.
- Compare its visible cell size and information density with the bundled coarse-density references.
- Run Perfect Pixel auto-detection as a diagnostic.
- Require `60–85` detected cells per axis, inclusive.
- Reject when either axis is below `60` or above `85`.
- Never resize, resample, sharpen, add detail, or force a grid to enter the accepted range.

The prompt's `24 × 24` language is a visual-simplification prior, not the
literal accepted source grid. Perfect Pixel's untouched-source detection is the
authoritative measurable density gate.

Treat the detected source grid as a preflight result. The density range applies to
the untouched source canvas only; it must not be re-applied to a semantic mask,
temporary working padding, or the final tight-cropped export grid.

Reject and generate a brand-new source when any of these defects appears:

- The portrait extends below the upper chest, sits too low, minimizes the head, or touches the canvas bottom.
- The source resembles a polished illustration or contains fine hair strands, micro-texture, mixed cell sizes, or insufficiently large color blocks such that automatic grid detection is unstable.
- The default pose becomes flatly frontal or full profile, hides an eye, or loses readable three-quarter depth.
- The eyes use different top/bottom rows or different iris/pupil row counts, their centers or gaze do not align, or the far eye is shorter or more than one logical cell narrower. Ignore sclera-only occlusion when judging eye height.
- The neck becomes a long narrow connector or the head looks detached from the collar and shoulders.
- The exterior pure-black outline is open, the bottom-most occupied row is not a continuous black baseline, or no clean background row remains below it.

Record, but do not reject solely for, minor blur, antialiasing, whole-cell tonal
transitions, a palette larger than the prompt target, or clusters of near-identical
colors. These are recoverable warnings when Pixel Fine converts them into stable,
semantically useful logical cells. Record the reconstructed-pixel difference and
logical palette count as diagnostics, but do not turn either metric into another
hard density gate. Make the final decision after refinement.

## Rejection and retry

- Start a fresh Stage 1 generation from the original request, approved identity brief, bundled references, and original user references.
- Do not use the rejected generated image as an edit target, attached reference, or recent-image context.
- Rebuild the retry exclusively from the fenced generation block in `generation-prompt.md`.
- Do not put detected counts, the accepted range, Perfect Pixel terminology, physical dimensions, or conversion settings into the retry prompt.

## User-provided source

- Preserve the source when the user requested direct conversion.
- Accept a binary transparent user source. Route it through Alpha preservation or conservative two-model repair; do not treat hidden RGB under transparent pixels as a background-color sample.
- Reject non-binary partial Alpha unless the user supplies a binary mask override.
- Edit it only when the user explicitly requested a local creative correction.
- If it fails the gate and editing was not authorized, preserve it and report the limitation. Do not refine it; start a separately authorized creative-edit route if the user wants it changed.

Record the detected grid, gate result, and rejection reason in the run metadata.
