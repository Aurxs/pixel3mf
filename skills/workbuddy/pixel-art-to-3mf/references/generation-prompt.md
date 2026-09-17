# Stage 1 — WorkBuddy Source-Generation Prompt

Read this file only while constructing an image-generation or explicitly requested image-editing call. Do not read post-generation references during this stage.

## Allowed inputs

For WorkBuddy native new-generation tasks, use text-only generation by default (`init-run --no-bundled-style`). The bundled coarse images can dominate the native image-editing model and copy their identity/scale. Use supplied or bundled style images only when the user explicitly asks for reference-guided generation. When references are requested, load:

- `../assets/reference-24x24-block-style.png` as Image 1
- `../assets/reference-coarse-density-a.png` as Image 2
- `../assets/reference-coarse-density-b.png` as Image 3
- For a clear action or handheld-object interaction, also load `../assets/reference-action-interaction.png` as Image 4

Treat user-provided images as references unless the user explicitly asks to edit the supplied image.

## Mandatory official-character research gate

Before every generation or creative edit of a named or recognizable character:

1. Search first-party sources for canonical identity, appearance, clothing, palette, props, and signature motifs.
2. Save `00_official_character_research.md` with the canonical name/version, 1–4 official URLs, verified visual facts, and clearly separated inferences.
3. Use the brief as the identity authority without copying logos, readable marks, slogans, or long source text.
4. Record original/non-character subjects as `official_character_research_status=not_applicable`.
5. Stop and ask for an approved reference when identity is ambiguous or no reliable official source exists.

## New-generation payload

Send only the text inside this block after replacing placeholders. Do not append any text from another skill file.

```text
创作一张角色像素头像：<character>。

构图第一：这是大头近景头像，只带少量肩膀，画面下缘止于锁骨下方的上胸。头部与发型占画面高度约三分之二。不要画到腰部、腰带、腹部或下半身，不要完整手臂。三分之四侧转、双眼清晰可见，表情自然可爱、轻松微笑。头发和饰品的最高点距离画布顶部至少3个完整逻辑格；左右至少留2格；主体底部至少留2格白边，任何发梢或描边都不能碰到画布边缘。

像素规格：整张正方形画布使用统一的 64 × 64 逻辑网格，白边也包含在网格内，再以最近邻放大为1024×1024像素PNG。每个逻辑格对应16×16输出像素，所有边缘与阶梯都落在这一格网上，不混用更细小的像素。角色造型简洁，以大色块概括头发、脸和服饰，约8–12种平涂颜色；减少细节，不要用密集小格增加纹理。

五官与轮廓：头部保持竖直，不歪头、不倾斜眼线。左右双眼放在同一条水平线上，两个瞳孔都用相同的3行格子，顶行和底行完全水平对齐，不要一高一低，远侧眼最多只窄1格；鼻子和嘴只用很少的格子，脖子短而自然。用一格宽的纯黑外描边包住完整主体，主体最低一行是连续黑色基线。保持原角色识别特征，不变成其他人物。

背景与质感：均匀纯白背景RGB(255,255,255)，整图完全不透明，所有Alpha=255；无损PNG。没有地面、背景物、阴影、透明、半透明、棋盘格、文字或水印。禁止渐变、抖色、细发丝、微小高光、抗锯齿、柔边、写实质感和混合像素尺度。如提供参考图，仅用于明确指定的身份或风格，不照搬其他人物，也不改变上述网格和留白。

角色身份依据（仅用于外观，不复制文字标志）：
<official-character-research-file>
```

## Explicit user-source edit payload

Use this block only when the user explicitly asks to edit their supplied source. Never use it to repair a generated result.

```text
Edit the supplied source with the minimum possible change. Preserve its composition, crop, pixel scale, palette, silhouette, head turn, face and jaw shape, hair mass, neck width, shoulder line, hand/prop placement, expression, and exterior outline. Correct only <user-requested defect>. Do not redesign or redraw unrelated areas.

Identity authority: Use the verified research brief below only to preserve canonical identity while making the requested local correction. Treat any unverified adaptation as inference. Do not add logos, readable marks, slogans, or text.

<official-character-research-file>
```

For every retry, start from the original request, identity brief, approved user references, and only the bundled references explicitly registered for that run. Keep text-only runs text-only. Never attach the rejected generated image.
