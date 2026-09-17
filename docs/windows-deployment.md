# Pixel3MF · Windows 部署指南

从解压交付包，到生成两份可切片的 3MF。

## 三步开始

1. 将 pixel3mf-windows.zip 完整解压到本地文件夹，例如 D:\pixel3mf。不要在压缩包预览窗口内运行。
2. 双击 01_install_windows.cmd，等待出现 Installation complete。第一次需要联网下载安装依赖。
3. 双击 02_convert_image.cmd，选择已有像素图片，按提示选择主体模型，等待转换完成。

成功后会打开 output 文件夹。进入最新的任务目录，取出 08_ 开头的两份 3MF。

## 使用前提

- 安装器面向 Windows 10/11、Intel 或 AMD 的 64 位系统。此安装包不支持 Windows ARM 或 32 位系统。
- 建议 16 GB 内存，并预留约 10 GB 磁盘空间；这是部署建议，未做最低配置实测。分割在 CPU 上执行，不要求独立显卡。
- 网络需要能访问 GitHub、Python 下载源和 Python 包索引。第一次使用语义分割还会下载模型权重。
- 不需要预装 Python、Git 或 uv。安装器把工具与环境放在项目目录中；不要复制其他电脑的 .venv。

## 这个包能做什么

双击转换入口负责“已有像素图 → 背景处理 → 网格整理 → 两种尺寸 3MF”。它不会自行调用 AI 生图，也不会自动把普通照片画成像素画。

文字生图、照片辅助重绘、通用像素与高保真任务，需由具备相关能力的 AI 按随包技能执行。技能分为 skills/codex/ 和 skills/workbuddy/，共用同一个项目。

---

# 01 / 首次安装

## 解压与启动

选择有写入权限的短路径，例如 D:\pixel3mf。避免放在 Program Files、网络共享盘或同步盘中。先完整解压，再双击 01_install_windows.cmd。通常不需要管理员权限。

命令窗口会依次显示五个阶段：下载 uv、准备 Python 3.12、准备 Lumina-Layers、安装依赖、检查环境。耗时取决于网络，窗口未报错时不要中途关闭。

## 安装器会准备什么

- .windows-tools/：项目专用 uv、Python 运行时和下载文件。
- .venv/：Windows Python 环境；.uv-cache/：依赖下载缓存。
- Lumina-Layers/：固定到随安装器指定的源码版本，避免每次部署自动追踪上游最新改动。
- output/setup/：安装日志，可用于排查失败原因。

环境检查只验证关键模块能导入、指定四色 LUT 存在、Lumina 栅格参数及 A1 mini 配置正确；不执行模型下载或完整转换。

## 如何判断成功

窗口出现 Environment check passed 和 Installation complete 后，按任意键退出，再运行 02_convert_image.cmd。

失败时不要继续转换。保留 output/setup/ 下最新日志，先解决最后一条错误，再重新运行安装器。已存在但不是该安装器管理的 Lumina-Layers，或来自 macOS 的 .venv，不会被自动覆盖；确认后将旧目录改名，再安装。

## 移动与重新部署

安装后请保持项目路径不变。若移动项目或换电脑，建议重新解压交付包并安装；虚拟环境不视为可搬运文件。旧的 output 成品可以单独保留。

依赖按 requirements 文件在安装时解析，尚未做到所有第三方包完全锁定。若未来安装出现兼容问题，把安装日志交给项目维护者。

---

# 02 / 选择图片并转换

## 准备输入

使用像素块清晰、主体完整的 PNG。也可选择 JPG、JPEG 或 WebP，但压缩与柔边可能影响网格检测。透明 PNG 应有明确的主体轮廓。

双击入口沿用 tools/run_pipeline.py，源图自动检测的网格检查包含每轴 60–85 格限制；不是任意尺寸的像素画都能通过。小逻辑图、普通照片或通用技能生成的其他网格，按相应 Skill 处理，不要靠放大图片或强行缩放绕过检查。

## 操作顺序

1. 双击 02_convert_image.cmd，在弹出的文件选择窗口中选择图片。取消选择不会开始转换。
2. 控制台输入 1 或直接回车：动漫主体模型；输入 2：通用主体模型。
3. 等待脚本处理。首次模型下载可能较慢，转换期间不要关闭控制台。
4. 成功后打开 output，进入最新的“时间戳_图片名”目录。

这里选择 2 只切换背景分割模型，并不切换为通用 Skill 流程，也不取消总入口的网格检查。保留的 Alpha 和背景孔洞仍会按原流水线规则检查。

## 取出成品

- 08_图片名_2x2.3mf：每个逻辑像素对应 0.84 mm。
- 08_图片名_3x3.3mf：已经完成 XY 补偿，每个逻辑像素对应 1.29 mm。
- 05_pixel_preview_8x.png：整理后像素图预览。
- 06_lumina_2d_preview_*.png：叠色预览，先检查颜色和背景。
- manifest.json：本次参数、处理记录和失败原因；07_ 开头的 ZIP 是 Lumina 原始归档。

成品默认包含 Bambu Lab A1 mini、0.4 mm 喷嘴、0.08 mm 工艺，以及红蓝黄白四色 LUT 对应配置。使用其他打印机或耗材时，需由操作者核对并调整切片配置。导入成品保持 100% 缩放，不再给 3x3 成品重复补偿。实际打印前仍需检查模型、耗材映射及切片预览。

---

# 03 / AI 工作流与问题排查

## 两套技能在同一项目中

skills/codex/ 包含 general-pixel-art-to-3mf、pixel-art-to-3mf-skill 和 high-fidelity-image-to-3mf。skills/workbuddy/ 包含 general-pixel-art-to-3mf 通用像素变体。两者共用 tools、profiles、Lumina-Layers 与 .venv，不需要切换分支或复制项目。

各技能的独立 Markdown 使用指南在 guides/skills/。按宿主选择一套同名技能，不要同时启用两份 general-pixel-art-to-3mf。可以让 AI 读取项目中对应的 SKILL.md；如需导入技能，选择具体技能目录，而不是 skills 总目录。

## 可复制的任务说明

```text
请在当前 Pixel3MF 项目中，读取适用于你所运行宿主的
skills/codex/general-pixel-art-to-3mf/SKILL.md
或 skills/workbuddy/general-pixel-art-to-3mf/SKILL.md。
参考我提供的宠物照片制作粗像素画，保留主要花纹，
按技能整理和验收后，导出 2x2、3x3 两份 3MF。
当前是 Windows，请使用 .venv/Scripts/python.exe，
将文档中的 POSIX 多行命令改成 PowerShell 可执行命令。
```

生图需要宿主本身提供生图能力。只交付 Skill 不会附带账户、API Key 或生图服务。原照片不重画、直接保留连续色调的需求，应使用高保真技能。

## 常见问题

- 下载超时：检查 GitHub 和包下载源的连接；安装失败重跑安装器。模型下载失败则重试转换，并保留失败日志。
- DLL 或运行库缺失：先按错误定位缺失组件；若明确提示 VC++ 运行库，可安装微软官方 Visual C++ x64 运行库后重试。
- 系统或组织阻止脚本：仅对确认来源的交付包按组织策略处理，不要关闭系统防护或擅自改全局执行策略。
- 网格检测不通过：检查是否确为清晰像素图，或改用对应技能的整理流程。
- 白色主体缺失或背景孔洞有歧义：查看遮罩预览和 manifest；不要为了通过而忽略歧义，需要针对图片修正遮罩。
- Lumina 启动失败：查看任务目录的 lumina_api.log，确认 8000 端口没有被其他无关程序占用。

求助时提供 output/setup/ 或 output/launcher/ 最新日志，以及失败任务的 manifest.json 和相关预览图。

---

# 04 / 维护者：手动构建交付包

## 在 GitHub 中触发

1. 将本次新增及移动的文件提交到仓库，并让 .github/workflows/windows-delivery.yml 存在于默认分支。
2. 打开仓库 Actions，选择 Build Windows delivery，再点 Run workflow 并选择要构建的分支。
3. 等待 Windows 安装检查通过，然后由 Linux 构建任务生成 PDF、完整交付 ZIP 和 SHA256 文件。
4. 在该次运行的 Artifacts 下载 pixel3mf-windows-delivery。解压 GitHub 的外层归档，将里面的 pixel3mf-windows.zip 和 PDF 转发给使用者。

工作流只有 workflow_dispatch 手动入口，不在 push 时运行，不创建 Release。Artifact 保留 14 天，若组织上限更短则需按仓库策略调整。日志也会上传，便于定位安装失败。

## 构建产物

- pixel3mf-windows.zip：包含项目工具、配置、两套技能、两个 CMD 入口及 PDF；不包含 .git、凭据、历史输出、macOS 环境、模型权重或 Lumina 软件本体。
- pixel3mf-windows-guide.pdf：同一份指南，供单独转发。
- SHA256SUMS.txt：ZIP 与 PDF 的校验摘要。
- 包内 BUILD-INFO.json：源码提交及 Windows 安装检查状态。优先交付 CI 检查通过的产物。

## 维护技能与重新打包

修改 Codex 通用技能或 skills/workbuddy/general-host-adapter.md 后，运行下面的同步脚本，再提交更新后的两套技能。CI 会检查生成结果是否已同步。

```text
python tools/build_general_workbuddy_skill.py
```

本地运行 tools/build_windows_delivery.py 会输出到 output/windows-delivery/。它需要 reportlab、pypdf 以及可用的中文 TrueType 字体；用 PIXEL3MF_PDF_FONT 指定字体路径。CI 会自动安装这些构建依赖。它们不是最终用户运行转换所需的额外安装步骤。

验证边界：本地构建本身不证明 Windows 安装成功；CI 会实际运行安装器和环境检查，但不执行生图、下载分割权重、完整 3MF 转换或实物打印。第三方网络与未来依赖变化仍可能导致部署失败。

参考：uv 安装文档 https://docs.astral.sh/uv/getting-started/installation/；GitHub 手动事件说明 https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows 。
