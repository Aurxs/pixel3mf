# WorkBuddy · 通用像素画转 3MF

技能入口：[SKILL.md](../../../skills/workbuddy/general-pixel-art-to-3mf/SKILL.md)。

## 适合做什么

适合人物、宠物、植物、物品、车辆、建筑和简洁场景的粗像素画，支持文字、照片和多图参考。也可转换已有像素画，或只交付经过整理的 PNG。

它与 Codex 变体使用同一个项目和 Python 环境；无需单独的 WorkBuddy 分支。请只启用 WorkBuddy 版本的同名技能。

## 开始前

先按 [Windows 部署指南](../../../README.md) 安装项目。在 WorkBuddy 中使用当前项目，让它读取上述技能；若导入技能，导入 `skills/workbuddy/general-pixel-art-to-3mf/` 整个文件夹。该文件夹包含 references、assets 和 scripts，不能只复制 SKILL.md。

需要新图时，WorkBuddy 必须提供可用的生图能力。技能和项目本身不附带账户或生图接口凭据。

## 示例指令

```text
请读取 skills/workbuddy/general-pixel-art-to-3mf/SKILL.md。
参考我提供的宠物照片，做一张完整坐姿的粗像素画，保留花纹和眼睛颜色。
生成纯白、不透明背景，再在本地处理背景，先 Perfect Pixel 整理，
再正式验收，最后导出 2x2、3x3 两份 3MF。
当前是 Windows，使用本项目 .venv/Scripts/python.exe。
```

```text
第一张照片负责主体外观，第二张只参考姿态。
请按 WorkBuddy 通用技能生成像素画，不把风格参考图的动物身份带进来。
只要整理后的逻辑像素 PNG 和放大预览，先不要转换 3MF。
```

## WorkBuddy 变体的规则

新生图固定采用纯白、不透明背景，之后在本地移除背景并保护白毛、眼白等前景。不要把 Codex 变体的优先透明生图要求混入该流程。图片需通过图像工具的实际参考图参数传入，不能只把路径写在提示词里。

该技能包含 `scripts/refine_pixel.py`，用于按本版本规则整理像素。它复用项目的背景与 3MF 转换工具；不要转而调用旧动漫候选验收入口或用总流水线的 60–85 门槛拒绝通用图像。

## 产物与检查

在新的 `output/` 任务目录保留源图、`04_pixel_perfect.png`、`05_pixel_preview_8x.png`、两个 Lumina 预览、两份 `08_*.3mf` 与 `manifest.json`。

先看白色特征是否保留、背景孔洞是否正确，再看叠色预览。最终 3x3 模型已做尺寸补偿，在切片器保持 100% 缩放。

如需直接把普通照片转 3MF 且不重画，应使用高保真工作流。WorkBuddy 目录另外提供[动漫人物技能](pixel-art-to-3mf.md)，但目前没有独立的 WorkBuddy 高保真变体。
