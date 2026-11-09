# Concise bead-post copy

Default to a fixed formula title, one sourced official character line and the actual chart information. Keep labels and prose Chinese. Use the reviewed Chinese character name; never invent a translation or personal reaction. Do not add an anecdote, personality hook, descriptive marketing paragraph, emotional ending or engagement question. Do not change historical works or posts.

## Title

`角色名拼豆图纸｜附镜像`

Replace only `角色名` with the verified Chinese name. Do not brainstorm another title, offer title alternatives or replace the title with the quotation. This is the post title; chart titles retain their existing rules.

## Official outfit/character line or acquisition voice

- Identify the depicted character and costume from the user-provided name or verified visual references. For a known outfit, prefer its own official skin description, release caption or a genuinely outfit-specific voice line. Do not use another costume's description. If the outfit is uncertain, do not invent its name; general character copy is an acceptable fallback.
- Outfit descriptions and voice resources must be checked separately. A costume's existence does not establish new acquisition dialogue. Use a costume-specific line only when the source identifies that costume or dedicated voice pack; otherwise retain the character's standard acquisition attribution.
- When no suitable outfit-specific line is verified, look for an existing official character tagline or introductory short line, or what the character says when first acquired. Useful source labels include `角色介绍` / `新增干员` / `宣传语` / `招聘合同` and `获得角色` / `首次获得` / `初次见面` / `干员报到`. In Arknights, `干员报到` is the acquisition self-introduction. A short recruitment description may also fit the intended character-summary line.
- Choose one yourself from these sources. Prefer a concise, recognizable line that represents the depicted character and fits the artwork. Once a suitable dedicated line is verified, do not keep searching unrelated dialogue for a more literary excerpt. Do not assume every game gives every character one unique, permanent slogan.
- Prefer official launch posts, character pages or game text/audio. A reliable character-specific wiki transcript is acceptable when primary material is unavailable. Verify the work, character/form, Chinese wording and source label. Do not confuse a recruitment description with a launch slogan, a character epithet with a spoken sentence, or official descriptive copy with the character's own speech. Exclude fan-created characters and fan slogans.
- Preserve the original Chinese wording. A short, contiguous excerpt is acceptable if its meaning is intact; mark it as `节选` in the separate source note. Do not splice lines, polish them into a poem or present your translation as official localization. Honor a source type or exact line explicitly chosen by the user.
- Put only the chosen line in quotation marks above the chart facts. Keep its source outside the copyable body, without adding an interpretation or an invented follow-up sentence. If no suitable official outfit description, character introduction or acquisition line can be verified, omit it and briefly state that outside the body instead of silently falling back to unrelated dialogue. Reuse an already verified source when available.
- When a run directory exists, retain the chosen text, character, verified outfit when applicable, source URL, source type, relevant label and excerpt status in `work/角色短句来源.md`. Do not build a large quote archive. In chat, use a compact `短句出处（正文外）` link. The source label should distinguish outfit-specific copy or voices from general character introductions, recruitment text and acquisition dialogue.

## Body

For an original/mirror pair:

```text
“{经核实的时装文案、角色短句或获取语音}”

角色：{中文角色名}
尺寸：{宽}×{高}格
色数：{实际色数}色
豆数：{实际豆数}颗
图序：{按本次实际上传顺序填写}
色卡：{实际使用色卡名称}
```

When the delivery also includes a 52-board version:

```text
“{经核实的时装文案、角色短句或获取语音}”

角色：{中文角色名}
原尺寸：{原向宽}×{原向高}格｜{原向色数}色｜{原向豆数}颗
52板：{该版实际宽}×{该版实际高}格｜{该版色数}色｜{该版豆数}颗
图序：{按本次实际上传顺序填写}
色卡：{实际使用色卡名称；不同版本使用不同色卡时分别注明}
```

For a verified non-default outfit, add `时装：时装名` below the character line; omit it if unverified. Keep the fixed post-title formula unchanged.

Read the current `manifest.json` and each delivered variant's saved `图纸数据.json` statistics and palette record; verify against the exported charts. Use the trimmed original dimensions and each 52-board chart's actual grid dimensions. “52板” describes that version; do not assume its dimensions, colors or bead total equal the original. Count only colors actually used and occupied bead cells. Each mirror shares its corresponding original's counts; do not double the total. Do not include a withdrawn or unaccepted variant. If statistics are missing, inspect the saved cells and derive them or report the missing field instead of guessing.

Match `图序` to the exact images being delivered: include the cover only if present, then identify every original and mirror shown. For example, a five-image upload may read `1封面，2原尺寸，3原尺寸镜像，4五十二板，5五十二板镜像`; a two-image upload has only its original and mirror. Never assume a fixed image count when a cover or variant is absent. Preserve the palette's verified name/model identifier instead of inventing a Chinese brand name; factual identifiers do not justify foreign-language prose.

Only an image is available: omit statistics that cannot be verified instead of estimating them from enlarged display pixels. Do not invent production time, difficulty, physical materials, personal experience, originality, price or collection instructions. Never describe a chart or render as a physical finished piece.

## Topics and delivery

Deliver one formula title, the concise body and, if useful, five to eight relevant Chinese topic suggestions in a separate `话题建议（正文外）` block. Do not append hashtags inside the body. Put the compact line reference in `短句出处（正文外）`. These labels and sources are outside the text intended for posting.

An explicit tutorial or collection request may add the necessary verified steps or existing-work details, while retaining the formula title and selected line. Do not expand to a target word count, multiple copy versions, slogan suggestions or engagement forecasts by default. Do not place the quotation on the artwork or on the character-name-only cover without a request to edit that image.

If saving a draft, use `work/小红书文案.md`, outside the primary PNG `delivery/` directory. With no run directory, respond directly in chat. Before delivery, quickly check the formula title, line provenance, numbers, variants and image order. A copy-only edit does not restart image generation or chart export. Preparing a draft does not authorize logging in or publishing.

Structure reference: [xiaohongshu-copywriting](https://github.com/maomao52088/xiaohongshu-automation-skills/blob/main/xiaohongshu-copywriting/SKILL.md). This skill's fixed title, sourced official character line and factual template take precedence over generic promotional writing patterns.
