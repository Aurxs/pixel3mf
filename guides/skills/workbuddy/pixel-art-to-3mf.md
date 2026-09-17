# WorkBuddy · 动漫人物像素画转 3MF

技能入口：[SKILL.md](../../../skills/workbuddy/pixel-art-to-3mf/SKILL.md)。这是此前 WorkBuddy 分支上的动漫人物版，现与其他技能一起在 `main` 维护。

## 适合做什么

适合动漫人物大头近景头像，带少量肩膀，保留人物身份、发型、服饰和眼睛特征。它使用 WorkBuddy 专用生图提示词、64×64 画布逻辑网格要求和候选图登记 / 验收流程，不是通用宠物、物品像素技能。

如果想制作动物、物品或自由构图，使用 [WorkBuddy 通用像素技能](general-pixel-art-to-3mf.md)。两套技能不要混用验收入口。

## 开始前

按[主 README](../../../README.md)完成环境安装。在 WorkBuddy 中打开当前 Pixel3MF 项目，读取 `skills/workbuddy/pixel-art-to-3mf/SKILL.md`；如果宿主支持导入技能，选择该文件夹及其完整资源。

Windows 可以先在项目根目录运行以下只读检查，不会调用收费生图：

```powershell
.\.venv\Scripts\python.exe tools/workbuddy_pixel3mf.py doctor
```

未配置 TokenHub/COS、Lumina API 尚未启动或未缓存模型权重可能显示警告，不代表 WorkBuddy 原生生图不可用。重点检查 `core_ready` 和具体错误。Mac 专用的 `configure-keychain` 不适用于 Windows。

## 示例指令

```text
请读取 skills/workbuddy/pixel-art-to-3mf/SKILL.md。
为宵宫制作动漫像素头像，先查官方角色资料，保留发型和服饰特征。
按技能的 WorkBuddy 专用提示词生成大头近景头像，只带少量肩膀，
使用原生生图并默认纯文字生成。登记候选图、完成验收后，
继续导出 2x2 与 3x3 两份 3MF，不要停在生图阶段。
当前是 Windows，使用 .venv/Scripts/python.exe。
```

```text
请使用 WorkBuddy 的 pixel-art-to-3mf 动漫技能，
将附件中已有的动漫像素图直接转换为两份 3MF，不重新生成。
保留原图；网格或背景存在问题时说明原因，不绕过验收。
```

## 执行过程

`tools/workbuddy_pixel3mf.py` 是这个技能的运行适配器，不是 ZIP 或 PDF 生成脚本。

- `init-run`：创建任务、记录请求，并保存本次提示词模板快照。
- `render-prompt`：输出原生生图需要的提示词、已登记参考图和目标目录。
- `import-candidate`：登记原生生图结果，保留原件并做限定范围的近白背景规范化。
- `decide`：记录候选图的视觉验收结论；接受后形成正式源图。
- `convert`：检查前置状态，调用本地转换流水线，保存两份成品与失败诊断。

完整参数用相应子命令的 `--help` 查看。每次生图仍需使用宿主真实可用的图像工具，并记录实际图像模型；不要把调度模型当成生图模型。

可选 TokenHub 生成需要操作者另行配置凭据；COS 回退额外需要 `cos-python-sdk-v5`。这些不是 WorkBuddy 原生生图与已有图片转换的安装前提，不要为使用默认流程强制配置它们。

## 验收与产物

新生成图使用纯白不透明背景，保留原动漫源图检查与最多三次候选尝试规则。重试不能把被拒绝的候选图作为参考。转换前必须接受一张候选，或按 direct 路径登记原图。

在 `output/<时间戳>_<角色名>/` 查看 `workbuddy_state.json`、原图与候选、像素预览、Lumina 预览、两份 `08_*.3mf` 和 `manifest.json`。3x3 成品已完成 XY 补偿，切片器保持 100% 缩放。完成后仍需对照源图检查眼睛、肩膀、外轮廓和底部基线是否完整。
