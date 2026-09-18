# Pixel source generation

Read at the generation stage only. New generation is permitted by a request to create/reinterpret a subject; existing-art conversion skips this stage. Inspect supplied images, distinguish identity, style and composition roles, and record visible features rather than inventing hidden details.

For a recognizable named character or branded figure, consult first-party sources for canonical identity, costume, colors and signature details. Save URLs and verified facts separately from inferences in `00_official_character_research.md`. Supplied references control the requested rendition. If the identity cannot be resolved, ask a focused question. Ordinary pets, people, objects and original subjects do not need fictional official research.

## References and composition

- General subjects/photos: inspect and attach `../assets/reference-corgi-pixel-style.png` for flat cells, stair-step contours and readable coarse detail only. Do not import the dog, pose or colors.
- Character portraits: inspect and attach `../assets/reference-character-style.png` for coarse block construction only. Preserve the requested character and pose, not the example's identity. Unless specified otherwise, use a readable head-and-shoulders composition, with complete hair and accessories inside the canvas. A requested full body or action overrides this default.
- A compatible user style reference takes priority over a bundled one. A user request for text-only generation omits style images.
- Photographs supply shape, distinctive markings and color patches. Simplify lighting and texture into flat pixel clusters. Do not beautify a person into anime, add a face to an object or humanize a pet unless requested.
- New isolated subjects prefer true transparent alpha; preserve opaque whites inside the subject. Intentional scenes retain their background. Use uniform opaque white only when the selected generator cannot provide transparency or the user requests it.

Save a brief containing user request, image roles, essential attributes, framing, background intent, and simplifications. The same foreground/background distinction controls later preparation.

## Generation prompt

Render only this block, replacing placeholders and omitting unused reference/correction lines. Attach actual files using the tool's documented image-reference mechanism. Do not paste this reference file into the generation tool.

```text
PIXEL ART GAME SPRITE. A tiny coarse pixel sprite enlarged with nearest-neighbor into big visible squares.

Subject: <brief subject identity, requested pose/framing and essential distinguishing features>.

Build the image from LARGE SQUARE PIXELS on ONE uniform grid. Each identifying feature occupies one or a few whole cells. Use about <subject-appropriate small palette, typically 8–12 flat colors>. Fill each cell with one completely flat color. Crisp block edges, simple stair-step silhouettes, a dark one-cell outline where useful. Simplify secondary details rather than making smaller pixels. Keep the complete requested silhouette inside the canvas with a clear margin. Preserve readable facial features and the requested viewing angle.

References: <map attached images to identity/composition/style; style examples control block construction only, never their subject>.

Background: <true transparent PNG with alpha-zero outside and opaque subject, no painted checkerboard; OR the single user-selected background>.

NO gradients, smooth shading, texture, glossy lighting, antialiasing, tiny sub-cell details, mixed pixel scales, painted checkerboard, unrequested text, watermark or grid annotations. This must look like a small retro game sprite enlarged into visible square cells.

Correction: <one observed visual defect, retries only>.
```

A user-requested grid target can be stated as the desired design scale, but the generated pixel dimensions are not proof of a logical grid. The refinement stage measures the result. Never sneak downstream detector thresholds or bead palette constraints into retries.

Explicit local edits use: “Edit the supplied image only to <requested correction>. Preserve unrelated identity, shape, composition, pixel scale, colors and background. Use references only for <authorized role>.” Otherwise generate anew from original references. At most two fresh retries for the same failure; preserve and disclose an unaccepted result at the limit.
