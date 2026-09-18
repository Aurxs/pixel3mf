# 项目目录与文件用途

下面展开维护中的项目文件。`Lumina-Layers/` 是独立第三方软件，环境、缓存和运行结果只列到目录层级。

```text
pixel3mf/
├── README.md                         项目首页；Windows 部署、使用、排错与 Action 操作
├── 01_install_windows.cmd            Windows 双击安装入口，调用 windows/install.ps1
├── 02_convert_image.cmd              Windows 双击选图转换入口，调用 windows/convert.ps1
├── requirements-pixel3mf.txt          本项目 Python 依赖
├── .gitignore                        排除环境、缓存、历史输出、dist 和第三方源码
├── .gitattributes                    指定图片、ZIP、PDF、3MF 等二进制文件属性
│
├── .github/workflows/
│   └── windows-delivery.yml          手动 Action：验证 Windows 安装，再打包项目源码
│
├── windows/
│   ├── install.ps1                   下载 uv/Python/Lumina、建环境、装依赖、检查安装
│   ├── convert.ps1                   弹出选图窗口、选择分割模型、运行转换并显示日志
│   └── check_environment.py          检查依赖导入、LUT、栅格参数与 A1 mini 配置
│
├── tools/
│   ├── beads/                      拼豆工作流、压缩、背景处理和图纸渲染，详见下文
│   ├── run_pipeline.py              原像素转换总入口，串联步骤并记录 manifest
│   ├── workbuddy_pixel3mf.py         WorkBuddy 动漫候选登记、验收、状态和转换适配器
│   ├── semantic_segment.py          在受时间/内存限制的 CPU 子进程中运行分割模型
│   ├── remove_background.py         按 Alpha 策略准备语义遮罩与背景处理结果
│   ├── refine_pixel.py              Perfect Pixel 网格检测、采样和逻辑像素整理
│   ├── cleanup_pixel.py             背景孔洞清理、二值 Alpha、歧义诊断及紧裁
│   ├── lumina_batch.py              Lumina 预览、双尺寸转换及成品处理
│   ├── three_mf_xy_scale.py         对 3x3 模型做幂等的 XY 43/42 尺寸补偿
│   ├── three_mf_a1mini_profile.py   为成品写入固定 A1 mini 项目配置
│   ├── prepare_square_canvas.py     旧版补方兼容工具，当前总入口不调用
│   └── remove_selected_white_holes.py
│                                   针对历史特定图片坐标的白孔修复；不是通用入口
│
├── profiles/
│   ├── README.md                   打印配置快照的来源、用途与更新注意事项
│   └── bambu_a1mini_0.4_0.08_extra_fine_pixel3mf.json
│                                   A1 mini 机器/工艺/耗材配置基线与项目覆盖值
│
├── skills/
│   ├── codex/
│   │   ├── general-pixel-art-to-3mf/    通用像素技能，详细结构见下文
│   │   ├── pixel-art-to-3mf-skill/      动漫角色像素技能
│   │   ├── high-fidelity-image-to-3mf/  高保真图像技能
│   │   └── pixel-art-to-beads/         独立拼豆技能，四图交付与 52 格压缩
│   └── workbuddy/
│       ├── general-pixel-art-to-3mf/    WorkBuddy 通用像素技能
│       └── pixel-art-to-3mf/            WorkBuddy 动漫人物像素技能
│
├── guides/
│   ├── project-structure.md         本文件：目录和文件用途
│   └── skills/
│       ├── README.md                技能选型和使用指南索引
│       ├── codex/
│       │   ├── general-pixel-art-to-3mf.md    通用像素操作示例
│       │   ├── pixel-art-to-3mf.md            动漫角色操作示例
│       │   ├── high-fidelity-image-to-3mf.md  高保真操作示例
│       │   └── pixel-art-to-beads.md         拼豆四图交付操作示例
│       └── workbuddy/
│           ├── general-pixel-art-to-3mf.md    WorkBuddy 通用像素操作示例
│           └── pixel-art-to-3mf.md            WorkBuddy 动漫人物操作示例
│
├── examples/
│   └── reference-action-interaction.png  动漫动作/互动像素参考图
│
├── tests/
│   ├── test_semantic_segment.py     分割子进程、资源限制和执行行为
│   ├── test_background_cleanup.py   背景处理、Alpha 与孔洞清理
│   ├── test_pixel_sizing.py         逻辑网格与物理尺寸计算
│   ├── test_pipeline_exports.py     流水线导出、共享任务目录和生图记录
│   ├── test_workbuddy_pixel3mf.py    WorkBuddy 候选状态、验收与转换适配测试
│   ├── test_beads.py                拼豆色卡、计数与背景处理测试
│   ├── test_bead_compression.py     压缩尺寸、轮廓与配色独立性测试
│   ├── test_bead_workflow.py        四张主图的交付与旧结果保护测试
│   ├── test_3mf_xy_scale.py         3MF XY 补偿与幂等性
│   └── test_3mf_a1mini_profile.py    A1 mini 配置规范化
│
├── Lumina-Layers/                   安装时下载的第三方叠色转换程序，不纳入本仓库
├── .venv/                          当前电脑的 Python 环境，不打包
├── .windows-tools/                 Windows 安装器下载的工具与 Python，不打包
├── .uv-cache/                      uv 依赖缓存，不打包
├── .cache/                         本地模型缓存等，不打包
├── .ruff_cache/                    静态检查缓存，不打包
├── .idea/                          本地 IDE 设置，不打包
├── .git/                           Git 元数据，不打包
├── tmp/                            临时文件和历史预览，不打包
├── result.json                     本地历史切片报告，不打包
└── output/
    ├── .gitkeep                    保留输出目录的空占位文件
    ├── setup/                      Windows 安装日志
    ├── launcher/                   Windows 选图转换日志
    ├── windows-delivery/           Action 临时生成的项目 ZIP
    └── <时间戳>_<主体名>/           每次任务的图片、预览、3MF 和 manifest
```

## 技能目录内部

### Codex 通用像素技能

```text
skills/codex/general-pixel-art-to-3mf/
├── SKILL.md                         AI 执行入口：输入路由、阶段边界、转换规则
├── agents/openai.yaml              Codex 技能展示信息与默认提示
├── assets/
│   ├── reference-corgi-logical.png      柯基逻辑像素参考
│   └── reference-corgi-pixel-style.png  柯基放大风格参考，只参考风格
└── references/
    ├── generation-prompt.md         生图提示词和参考图使用规则
    ├── source-acceptance.md         原图轻量预检与处理路径选择
    ├── pixel-refinement.md          Perfect Pixel 整理和正式验收
    └── lumina-conversion.md         精确尺寸、叠色预览和双版本 3MF 导出
```

### Codex 动漫角色像素技能

```text
skills/codex/pixel-art-to-3mf-skill/
├── SKILL.md                         动漫角色研究、生图、验收和转换入口
├── .gitignore                       技能目录自己的忽略规则
├── agents/openai.yaml              Codex 技能展示信息
├── assets/
│   ├── reference-24x24-block-style.png  大块像素风格参考
│   ├── reference-action-interaction.png 动作/互动参考
│   ├── reference-coarse-density-a.png   粗像素密度参考 A
│   └── reference-coarse-density-b.png   粗像素密度参考 B
└── references/
    ├── generation-prompt.md         动漫人物生图要求
    ├── source-acceptance.md         动漫源图验收和网格约束
    ├── pixel-refinement.md          动漫像素整理步骤
    └── lumina-conversion.md         Lumina 导出步骤与参数
```

### Codex 高保真技能

```text
skills/codex/high-fidelity-image-to-3mf/
├── SKILL.md                         高保真生成、参考创作或原图直接转换入口
├── agents/openai.yaml              Codex 技能展示信息
└── references/
    ├── generation-prompt.md         细节图像的生成与编辑要求
    ├── workflow.md                  高保真准备、预览与 3MF 转换步骤
    ├── default-parameters.md        默认尺寸、LUT、背板和建模参数
    └── troubleshooting.md           高保真转换问题排查
```

### Codex 独立拼豆技能

```text
skills/codex/pixel-art-to-beads/
├── SKILL.md                         输入路由、四图交付、默认 52 格压缩
├── agents/openai.yaml              Codex 展示信息与默认调用
├── assets/                         像素风格参考、MARD 色卡及来源许可
└── references/
    ├── generation-prompt.md         新像素画生成与参考图规则
    ├── pixel-refinement.md          背景处理、Perfect Pixel 与验收
    ├── compression.md              精确尺寸、轮廓保护与 AI 整理
    ├── bead-export.md              四图入口、输出目录与排版
    ├── palette-format.md           色卡和可编辑数据格式
    └── runtime.md                  项目运行路径与来源信息
```

```text
tools/beads/
├── run_workflow.py              四图工作流 prepare / finish 入口
├── compress_pixels.py           尺寸压缩、通用提示词及 AI 输出检查
├── bead_pattern.py              单尺寸原向/镜像图纸渲染
├── bead_palette.py              色卡校验与颜色匹配
├── prepare_source.py            原图到逻辑像素网格
├── remove_background.py         独立背景处理实现
├── semantic_segment.py          可选分割子进程
├── cleanup_pixel.py             语义网格清理
└── requirements*.txt            基础、精修和可选抠图依赖
```

拼豆规则与资产在技能目录，程序在项目 `tools/beads/`，不依赖其他技能或 Lumina；开发测试与其他项目测试一起放在 `tests/`。交付图位于任务的 `delivery/`，中间产物和辅助文件位于 `work/`。

### WorkBuddy 通用像素技能

```text
skills/workbuddy/general-pixel-art-to-3mf/
├── SKILL.md                         WorkBuddy 执行入口，包含宿主专用生图规则
├── scripts/refine_pixel.py          随技能提供的像素整理助手，复用项目 Python 环境
├── assets/
│   ├── reference-corgi-logical.png      柯基逻辑像素参考
│   └── reference-corgi-pixel-style.png  柯基放大风格参考
└── references/
    ├── generation-prompt.md         WorkBuddy 纯白不透明背景生图要求
    ├── source-acceptance.md         原图预检与背景准备规则
    ├── pixel-refinement.md          像素整理与验收规则
    └── lumina-conversion.md         双尺寸叠色 3MF 导出规则
```

`skills/` 中的规则给 AI 执行；`guides/skills/` 中的说明给使用者阅读。拼豆图纸的 PDF/CSV 为任务内辅助产物；项目交付 Action 直接归档 Git 跟踪的项目文件。

## WorkBuddy 动漫人物技能目录

```text
skills/workbuddy/pixel-art-to-3mf/
├── SKILL.md                         动漫人物专用执行入口及 WorkBuddy 宿主规则
├── assets/
│   ├── reference-24x24-block-style.png   可选大块像素风格参考
│   ├── reference-action-interaction.png 动作/互动参考
│   ├── reference-coarse-density-a.png   可选粗像素密度参考 A
│   └── reference-coarse-density-b.png   可选粗像素密度参考 B
└── references/
    ├── generation-prompt.md         WorkBuddy 中文头像提示词与 64×64 画布要求
    ├── source-acceptance.md         候选文件、近白规范化与源图验收规则
    ├── pixel-refinement.md          背景和逻辑网格整理规则
    └── lumina-conversion.md         预览、双尺寸 3MF 与成品记录要求
```

默认原生生图不附加内置风格图，明确要求参考图时才使用这些资源。这个技能通过 `tools/workbuddy_pixel3mf.py` 执行，与通用技能分开选择。`.workbuddy.local.json` 是可选的本机提供商配置，已忽略，不进入源码包。
