# High-Fidelity Generation Guidance

Use this reference only for image generation or creative editing. For direct conversion, preserve the supplied image and create only conversion-required derivatives.

Complete character research when required, then adapt the following prompt.

```text
Create <subject and action> as a polished, detailed raster image for a layered 3MF plaque.

Identity: Follow the user's request and, when present, the verified character brief at <research-file>. Keep inferred details distinct from verified traits. Do not reproduce logos, slogans, or readable marks.

Composition: Use one clearly readable subject on a square canvas with a clean silhouette and enough margin for preparation. Unless requested otherwise, use a natural portrait or upper-body composition. Include no text, watermark, UI, frame, or extra subject.

Rendering: Preserve smooth curves, antialiasing, small identifying details, natural gradients, coherent shading, material texture, and high-resolution anatomy in the requested photographic, illustrative, anime, painterly, or rendered style. Keep important features readable at the configured physical size.

Print awareness: Avoid extremely thin disconnected elements. Keep subject/background separation clear when a transparent plaque is intended. Do not pre-reduce the palette for the selected LUT; let Lumina map the colors.

Avoid pixel art, logical grids, nearest-neighbor enlargement, deliberately low resolution, stair-stepped contours, duplicated features, malformed anatomy, and accidental clutter.
```

## Reference-guided work

Inspect the upload and state which requested properties will guide the target: identity, costume, palette, medium, pose, lighting, composition, mood, or another named trait. Do not assume all source details should transfer.

For a local correction, change only the named defect. Preserve accepted composition, crop, identity, geometry, palette, lighting, texture, edges, background treatment, and resolution.

## Acceptance

Regenerate or edit a generated target when it is pixelated, unexpectedly low-resolution, off-identity, compositionally wrong, or contains accidental text, watermark, duplicate subjects, or obvious generation artifacts. Do not creatively reject or redesign a direct-conversion source; report its limitations instead.
