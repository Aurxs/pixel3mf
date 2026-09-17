# Stage 1 — General Subject Generation

Read only for generation or an explicitly requested edit. No later-stage settings belong in the generation payload.

## Interpret references

Inspect each supplied image before constructing the prompt. Use the image-generation tool's supported reference-image mechanism; a path mentioned in prompt text alone is not an attached reference. If a local file is available, inspect it and attach that file. If only conversation images are available, use the smallest supported recent-image context that includes the intended inputs without including rejected results.

- A **subject reference** controls visible identity, outline, proportions, distinctive markings, or parts. For photos, retain distinguishing visible details while simplifying lighting, texture, and perspective into pixel clusters.
- A **style reference** controls block scale, outline, palette treatment, or shading only. Do not import its subject or accessories.
- A **composition reference** controls viewpoint, framing, placement, or pose only.
- For multiple images, state each role explicitly. Prefer the user's explicit priorities; otherwise use the clearest subject view for structure and other views for supporting details. Ask only if conflicting identities or designs cannot be reconciled without inventing the intended subject.
- Separate observable facts from assumptions. Do not infer a person's name or hidden details from a photo. Do not beautify a person into an anime character, humanize an animal, or add facial features to an object unless requested.
- Default to an isolated subject with its important silhouette visible. A person can be a portrait or full figure; a pet can sit or stand; objects and buildings use an informative view. Follow the requested framing. Do not force an upper-chest crop, three-quarter face, equal eye templates, oversized head, neck ratios, or straight bottom baseline.
- For a requested scene, use a compact coherent vignette with simplified major elements. Keep meaningful scenery inside the subject group; only the outside canvas is removable background. Do not erase sky, snow, windows, or white surfaces just because they are pale. If a panel border or base is useful, use one consistent with the requested design.

Use supplied references as the visual authority for the requested rendition. For a named fictional character, mascot, or branded design, research first-party sources when canonical details are needed. Save any research in `00_official_character_research.md` with source URLs and verified facts versus inferences. Ordinary people, animals, objects, and scenery do not require invented “official character” research; record `not_applicable`. If identity is uncertain, preserve observed appearance or ask a focused question instead of guessing.

### Default pixel-style references

Unless the user supplies a stronger compatible pixel-style reference or explicitly requests text-only generation without style images, inspect and attach this one style image:

- [reference-24x24-block-style.png](../assets/reference-24x24-block-style.png)

It controls only large pixel blocks and flat color clusters. Do not attach `reference-coarse-density-a.png` or `reference-coarse-density-b.png` by default: they contain gradients that conflict with the flat-fill target. Keep those files as historical examples, not positive shading references. Never copy the style image's character, human anatomy, crop, pose, palette, clothes, or accessories into the requested subject. Keep user subject/photos separate from style inputs in the reference mapping. “No user reference photo” does not mean “no style reference”; describe the actual attachments accurately.

Save the selected reference roles, observable attributes, composition, requested endpoint, and simplifications in `00_subject_brief.md` before generation. Do not substitute photo realism for the attached pixel style.

## New-generation payload

Replace placeholders with a one-sentence subject description, a short palette of six to eight subject-appropriate colors, the selected background instruction, and a brief mapping of attached images. Omit reference and correction lines when unused. On retries, add just one concrete visual correction. Keep the complete payload short; do not paste this file's explanatory rules into it or append later-stage constraints.

Keep the pixel-art specification first in the rendered prompt. Limit the subject brief to its essential silhouette, colors, and a few distinguishing features; express these as pixel clusters. A photograph supplies subject information, not rendering style. Do not expand the prompt with requests for realistic lighting, natural material texture, fine anatomy, lifelike detail, or polished illustration. When a requested feature is too small for the coarse grid, simplify it rather than reducing the pixel size. Preserve explicit user priorities if they override a default.

Choose one background instruction before calling the generator; insert only that choice in the payload so opaque and transparent requirements never conflict:

- **Preferred, transparency supported:** “Transparent PNG, background=\"transparent\": real alpha-zero empty background, solid opaque subject. Keep white subject features opaque. No painted checkerboard.”
- **Fallback, transparency unsupported:** “Opaque PNG on uniform pure white RGB (255, 255, 255), alpha 255 everywhere. No background texture or shadow.”
- **User-specified background or intentional scene:** describe that background and preserve the requested scene content. Do not replace it with a cutout by default.

Use the selected tool's documented transparency support rather than inventing a tool parameter or changing models. For the built-in image tool, request real transparency in the prompt. A failed transparent result is a candidate needing correction, not proof that the tool lacks support.

```text
PIXEL ART GAME SPRITE. A tiny 24×24 pixel sprite enlarged with nearest-neighbor into big visible squares.

Subject: <one sentence describing the subject, requested framing/action and essential features>.

Build the subject from only a few LARGE SQUARE PIXELS on ONE uniform grid. Each small identifying feature occupies only one or a few whole cells. Use only these solid colors: <six to eight subject-appropriate colors>. Fill every region with one completely FLAT color, like the bucket-fill tool in a pixel editor. Crisp block edges. Simple stair-step silhouette. Dark one-cell outline where needed. Sacrifice secondary detail for large readable blocks. Keep the requested subject inside the canvas with a clear margin.

References: <brief image-role mapping; subject photos supply shape and color patches only; the style image supplies block construction only, never its character>.

<selected background instruction>.

NO smooth shading, NO gradients, NO lighting effects, NO texture, NO glossy finish, NO tiny detailed pixels, NO antialiasing, NO painted checkerboard, NO unrequested text or decorations. This must look like a tiny retro videogame sprite enlarged into big squares.

Correction: <one observed visual defect on a retry; omit this line for a first attempt>.
```

## Explicit local edit payload

Use only for an explicit request to correct a user-provided source. A broad request to reinterpret a photograph as pixel art uses the generation payload with that photograph attached as a reference.

```text
Edit the supplied image only to <requested correction>. Preserve all unrelated subject identity, shape, proportions, distinctive markings, composition, crop, pose, palette, pixel scale, background and alpha. Use the attached references only for <requested reference roles, or none>. Do not restyle or redesign unrelated regions.
```

Inspect the result before continuing. For a failed generated result, generate afresh from the original inputs within the entrypoint's retry limit. Do not attach the rejected image. An explicitly edited user source retains the user's requested background/alpha; do not change it merely to enforce a new-generation default.
