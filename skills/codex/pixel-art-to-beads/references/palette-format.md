# Palette and saved project formats

Default: `assets/palettes/mard-221.json`. Source: [maxcleme/beadcolors](https://github.com/maxcleme/beadcolors/tree/29229889daab404fb30531d4bb785fd73f7f58e3), MIT. Upstream CSV and license are bundled. The 221 colors are the A-H and M groups from that pinned source. Values are community RGB approximations, not verified manufacturer measurements; do not mix values from other web palettes silently.

Custom JSON:

```json
{
  "id": "my-palette-v1",
  "name": "我的色卡",
  "version": "1",
  "source": "user supplied",
  "colors": [
    {"code": "W1", "rgb": [255, 255, 255]},
    {"code": "B1", "rgb": [0, 0, 0]}
  ]
}
```

Or UTF-8 CSV with `code,hex` header. Codes are unique 1–12 ASCII letters/digits/underscores/hyphens, RGB integer channels 0–255. Up to 4096 colors. Duplicate or malformed values fail before rendering. User-defined codes must not be presented as MARD codes.

Matching converts sRGB to CIELAB D65 and minimizes Delta E 76 (not CIEDE2000). No dithering. An optional cap uses deterministic frequency-weighted greedy selection among the available palette colors; locked colors remain available as anchors. It is a heuristic, not a guarantee of perceptually optimal or semantically aware reduction. Review key facial/outline colors. `allowed` restricts candidates to owned colors. `locked` does not paint extra cells or force unused colors into the artwork.

Saved `图纸数据.json` has schema `pixel-art-to-beads/v1`, title, embedded full palette, source provenance/hash, mapping parameters, and `cells`: a rectangular array of color codes or JSON null. Row zero is the top, column zero the left. Null means no bead; white is an ordinary non-null color code. Normal data is canonical; mirror data is derived by reversing each row. Rendering recomputes all counts, ignoring stale saved statistics. Invalid grids fail.

JSON also records orthogonal connected components and rendering settings. `rendered_needs_visual_review` is a technical completion state, not visual acceptance. After review, save evidence in `review.json` and mark the project `accepted`.
