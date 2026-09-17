# Codex · 高保真图像转 3MF

技能入口：[SKILL.md](../../../skills/codex/high-fidelity-image-to-3mf/SKILL.md)。

## 适合做什么

适合照片、细节插画、渲染图及连续色调图像，尽量保留细节、平滑边缘与渐变。支持从文字生成、参考图辅助创作，以及原图直接转换。它不制作粗像素画，也不运行 Perfect Pixel。

## 说清楚你的目标

- 直接转换：提供原图，说明不重画、不改风格。
- 参考图创作：说明参考外观、姿态、构图或风格中的哪部分。
- 文字生成：说明主体与构图；可识别角色的生成 / 编辑会先查官方资料。
- 如果默认 65 mm 方形不合适，请明确目标尺寸与如何处理长宽比。

## 示例指令

```text
请读取 skills/codex/high-fidelity-image-to-3mf/SKILL.md。
把附件照片直接转成高保真叠色 3MF，不重画，不像素化。
保留原文件，按默认 65 mm 方形规格准备图像，避免裁掉主体。
先生成并检查 Lumina 预览，再导出模型和参数记录。
```

```text
请使用 high-fidelity-image-to-3mf，参考这张照片中的宠物外观，
生成一张细节丰富的插画，再导出高保真 3MF。
保留眼睛颜色和胸前花纹，主体轮廓清晰。
```

## 默认参数与输出

默认物理尺寸 65×65 mm、背板 1.2 mm、双面结构、不加挂孔、BambuLab PLA 红蓝黄白 LUT、Lumina high-fidelity 模式。若指定不同需求，执行时应记录实际参数。

典型产物包括 `01_source.*` 原件、`02_target_image.png` 目标图、`04_square_prepared.png` 转换输入、`05_lumina_2d_preview.png`、`06_lumina_batch_result.zip`、`07_主体名.3mf` 和 `manifest.json`。

## 与像素流程的差别

这里不导出像素流程的 2x2 / 3x3 两套模型，也不应用 43/42 的像素 XY 补偿。保留 Lumina 生成的项目和切片设置，不应直接套用像素总入口的全部参数。

`02_convert_image.cmd`、`tools/run_pipeline.py` 和当前像素版 `tools/lumina_batch.py` 都不是此工作流的直接入口。需要让 AI 按技能引用的高保真工作流调用 Lumina。

“高保真”描述处理方式，不代表四色叠色打印能逐像素复现屏幕颜色。交付前检查叠色预览，实际打印前核对设备、耗材与切片设置。
