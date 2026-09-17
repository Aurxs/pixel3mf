# Skill 使用指南

这些是给使用者阅读的说明；AI 执行规则仍以对应 `SKILL.md` 为准。

| 运行宿主 | 需求 | 指南 |
| --- | --- | --- |
| Codex | 宠物、人物、物品、植物等通用粗像素画 | [通用像素画](codex/general-pixel-art-to-3mf.md) |
| Codex | 动漫角色像素画，沿用专门的人像与源图规则 | [动漫角色像素画](codex/pixel-art-to-3mf.md) |
| Codex | 照片、插画直接转换，保留连续色调与细节 | [高保真图像转 3MF](codex/high-fidelity-image-to-3mf.md) |
| WorkBuddy | 通用粗像素画，使用宿主生图和白底处理流程 | [WorkBuddy 通用像素画](workbuddy/general-pixel-art-to-3mf.md) |
| WorkBuddy | 动漫人物头像，使用专用提示词与候选验收流程 | [WorkBuddy 动漫人物](workbuddy/pixel-art-to-3mf.md) |

## 先完成项目部署

Windows 用户按 [Windows 部署指南](../../README.md) 操作。两套技能共用当前项目的 `tools/`、`profiles/`、`Lumina-Layers/` 与 `.venv/`，无需独立分支或第二套环境。

Windows 使用 `.venv/Scripts/python.exe`；macOS/Linux 使用 `.venv/bin/python`。文档中的 POSIX 多行命令需要按实际终端改写。

## 如何开始任务

在能访问本项目的 AI 中，直接提供对应 `SKILL.md` 路径并要求读取执行。若宿主支持导入或安装技能，导入具体的技能文件夹；不要把 `skills/`、`skills/codex/` 或 `skills/workbuddy/` 当成一个技能。

同名的 Codex / WorkBuddy 通用技能只选适合当前宿主的一份。文字生图和参考图重绘需要宿主有生图能力，技能包不包含账户、凭据或图像服务。

生成结果保存在 `output/` 的独立任务目录。Pixel 流程默认交付两份尺寸不同的 3MF；高保真流程默认交付 65 mm 方形模型，二者不能混用入口与缩放规则。
