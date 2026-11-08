# Pixel Eye Inspection and Repair

Based on the trialed v2.1: repair the eye shape and lower contour first, then the gaze center, and finally the highlights.

## When to use

Always enter this process after pixel refinement and background correction have produced the actual logical pixel image. This step selects an image for final acceptance; it does not decide regeneration or whether Stage 3 passes. When creative editing of a user-provided image is not authorized, inspect and preserve the input, and pass any observed issues to final acceptance.
First check whether the eyes need repair. Preserve natural, clear eyes; do not create changes merely to demonstrate a repair.
The Agent performs inspection, repair and review without requiring the user to specify pixel coordinates.

## Inputs

- Required: the refined logical pixel image.
- Optional: the corresponding original generated image, to identify details lost during sampling.
- Optional: user-approved pixel-eye references, to understand eye shapes, shading and highlights.
- Optional: character appearance references, to confirm eye colors and distinctive designs.

Without the original generated image or additional references, inspect the current image directly; do not require more material.
References guide the rendering approach, not direct copying of eye shapes, colors or pixel arrangements. The original generated image may also have defects; do not treat it as a mandatory pixel-by-pixel restoration target.

## 1. Inspect the refined eyes

View both the complete portrait and a nearest-neighbor enlarged face.
Identify each eye's upper and lower lids or outlines, sclera, iris, pupil or darker gaze center, and highlights.
Low-resolution styles may combine some structures; do not require five separately distinguishable parts in every eye.
Check for:

1. Missing corners, breaks or displaced iris/pupil pixels that cannot be explained by eyelids or hair occlusion.
2. Eye shapes and sizes that do not fit the face angle, or an obvious imbalance.
3. Inconsistent gaze, unintended crossed eyes or diverging sight lines.
4. Sclera crowding the iris or merging with highlights so the eye appears to have a hole.
5. Unclear light/dark structure, leaving a uniform color block without a gaze center.
6. Unexplained dangling blocks or broken tails along the lower iris, or color extending onto the face like a tear streak.
7. Missing, conflicting or oversized highlights, or highlights that fragment the eye.

The eyes need not be identical. Preserve reasonable differences caused by perspective, occlusion, expression and character design.
Do not substitute equal pixel counts for visual judgment, or explain every missing corner as perspective.

## 2. Set the repair goal

Plan local changes only for observed problems:

- Original looks natural but refinement damaged it: prioritize restoring the original eye shape, gaze and key details.
- Original is also unnatural: allow rearranging a few color blocks inside the eyes.
- Structure is sound but the eyes look lifeless: first check for missing tonal contrast or highlights, rather than immediately redrawing the whole eye.
- No clear problem: leave it unchanged.

Do not aim for identical eyes or a white dot in every eye.

## 3. Repair eye shape and internal structure

Address eye shape, iris and gaze before highlights.

- Keep the eye outline clear, avoiding meaningless gaps and overly thick black frames.
- Make the iris read as a coherent whole by correcting unnatural missing corners, fragments or protrusions. Connecting the iris does not mean expanding it in every direction or filling the eye interior. Check iris width, sclera space and eyelid contours together to avoid a broad, heavy iris block. Keep reasonable tapers, steps and sclera gaps; they need not be filled.
- Inspect the lower iris contour separately: end the eye's color blocks with a coherent curve or stepped edge. Do not retain dangling cells merely because their color resembles the iris when eye shape, perspective or occlusion does not justify them.
- Remove unnecessary lower protrusions or adjust adjacent iris blocks to join naturally; do not default to painting everything skin-colored. Keep edits within the eye regions and preserve every Alpha value.
- Allow reasonable curves, tapers and asymmetry. Do not align both lower edges or cut the eyes into rectangles.
- Retain enough sclera to convey eye shape and direction, without requiring a complete white ring.
- Restore a darker gaze center when needed, without imposing black pupils on every style. Use deep blue, purple or another dark color compatible with the image. Assess its contrast with the iris; do not turn soft eyes into heavy black blocks merely to emphasize gaze.
- Express shading with local color blocks, not continuous gradients or fine noise.

Use the smallest changes that solve the complete local problem. Do not insist on changing only one cell or expand the task into redrawing the whole face.

## 4. Inspect and repair highlights

Highlights convey reflections and improve eye readability; they are not mandatory decoration.

- Prefer preserving a reasonable original highlight direction and the character's eye style.
- When adding highlights, place them appropriately in or near the iris/pupil while retaining enough colored area and a gaze center.
- Follow a clear, reasonable existing light direction. Without usable lighting cues, use soft frontal light from the viewer/screen direction as a stylized default; do not claim this determines exact reflection coordinates.
- Consider head turn, eye orientation and light together so both eyes reflect the same lighting relationship. Do not fix highlights to the upper left or upper right, or mirror them mechanically.
- Pupil position conveys gaze; highlight position conveys reflection. Do not move highlights as a substitute for adjusting gaze or require highlights to translate with the pupils. Allow natural adjustments when the character's orientation changes, but do not use a rule such as "facing left always means a left-side highlight."
- Place both highlights at corresponding lit positions within their respective irises; they need not share a canvas row or column.
- The farther or occluded eye may use a smaller, simpler highlight.
- Use a bright color clearly distinguishable from its surroundings, not necessarily pure white.
- Distinguish sclera, bright iris areas and specular highlights; do not turn every light color white.
- Scale highlights to the actual eye size, without a fixed cell count.
- Do not force an independent highlight into extremely small, closed or substantially occluded eyes.

After adding highlights, check that they read as reflections rather than sclera gaps, holes or floating bright dots.

## 5. Edit scope and file preservation

- Preserve the original and save repair candidates separately.
- Edit only explicitly bounded small regions around the two eyes.
- Preserve the logical grid, image dimensions and every Alpha value.
- Do not change the mouth, face shape, hair, clothing or other regions.
- Do not resample the whole image or call an image-generation model to redraw it.
- Prefer existing local colors. When needed, sample the original or add a few eye colors with a clear purpose.
- Do not reduce colors or compress the whole-image palette at this stage.
- Record actual changed coordinates, before/after colors and reasons.

Programmatically confirm that changes occur only within the eye regions and all other pixels remain identical. This verifies edit scope, not visual quality.

## 6. Compare and select candidates

Produce before/after comparisons at matching scales for both the complete portrait and the enlarged face.
The Agent must view both comparisons and assess:

- Whether eye shapes are complete and natural, without unexplained missing corners; whether lower iris contours end clearly without dangling tails.
- Whether eye size relationships and gaze are coherent.
- Whether iris, sclera and highlights remain distinguishable.
- Whether highlights improve expression rather than damage eye structure.
- Whether character identity and expression are preserved.
- Whether the complete portrait looks more natural than before.

Do not judge success solely by increased symmetry, added highlights or a small edit count.
After the first candidate, view the complete portrait and enlarged face to identify specific remaining visual problems. Before making a second candidate, check whether the first looks natural within the complete portrait. If the iris is overfilled or sclera has been reduced, roll back those changes. Keep only the parts that actually look better, then address the remaining problems. For example, when highlights merge with sclera, first try adjusting their color without simultaneously changing highlight position, pupils and eye shape. Build both candidates by applying each complete edit plan to the untouched original. The second may reuse effective edits; it need not redesign the whole eye. Compare the original and candidates, then choose the more natural result.
If no candidate clearly improves the image, retain the original; do not accumulate endless edits on successive repairs.
Try at most two local candidates. If neither improves the image, select the original, retain the candidates and describe unresolved issues, then hand off to Stage 3 final acceptance. This step does not regenerate images or declare overall acceptance.

## Avoid copying a single successful example

These rules prescribe no fixed pupil length, highlight cell count, mouth shape, color values or edit coordinates.
A few successful edits in one example do not mean every image should receive the same changes.
Do not select a candidate merely because it is described as "more lively": check whether structure, lower contours, gaze, highlights and the complete portrait improve together.

## Outputs

- The untouched original.
- The selected candidate and its path; select the untouched original if there is no improvement.
- Before/after comparisons of the complete portrait and enlarged face.
- A brief change record, selection rationale and unresolved issues for Stage 3 final acceptance.

If color reduction or 3MF conversion follows, check again that key eye structures and highlights have not merged or disappeared.
