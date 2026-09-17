# pixel3mf：像素画转叠色 3MF

本项目在本地串联以下步骤：已有图片 → 原图网格预检 → IS-Net 语义遮罩 → Perfect Pixel 矩形网格整理 → 逻辑格背景孔洞清理 → 紧裁导出网格 → 精确动态尺寸 → Lumina-Layers batch API → 叠色 3MF。每次运行都会在 `output/<timestamp>_<slug>/` 新建目录并保留中间文件。

Python 脚本不直接调用 Codex image generation。先在 Codex 中生成图片，或准备自己的参考图，再把本地图片路径交给总入口。

## 初次部署

外层仓库不包含 `Lumina-Layers/` 软件本体；该目录已加入 `.gitignore`，每次部署时在项目根目录重新 clone。这样可以避免把叠色软件源码和它自己的输出、缓存一起提交到本项目。

```bash
git clone <本项目 GitHub 私有仓库地址> pixel3mf
cd pixel3mf
git clone https://github.com/lumina-layer-studio/Lumina-Layers.git Lumina-Layers
```

如果 `Lumina-Layers/` 已经存在，确认它来自上述仓库即可；需要更新时运行：

```bash
git -C Lumina-Layers pull --ff-only
```

然后创建项目环境并安装两个项目的依赖：

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -r Lumina-Layers/requirements.txt
uv pip install -r requirements-pixel3mf.txt
```

`skills/` 是随本项目分发的 Codex skill 文件夹，不是压缩包。按任务选择：

| Skill | 适用任务 |
| --- | --- |
| [pixel-art-to-3mf](skills/pixel-art-to-3mf-skill/SKILL.md) | 原有动漫角色像素画，保留角色上半身、眼睛和姿态专用规则 |
| [general-pixel-art-to-3mf](skills/general-pixel-art-to-3mf/SKILL.md) | 通用粗像素画：人物、宠物、植物、物品、车辆、建筑和简洁场景；支持文字、参考图或实拍照片辅助生成，也可导出 3MF |
| [high-fidelity-image-to-3mf](skills/high-fidelity-image-to-3mf/SKILL.md) | 保留照片、插画的连续色调和高精细节，使用非像素转换流程 |

通用版示例：“使用 `$general-pixel-art-to-3mf`，参考这张我家猫的照片做粗像素画，保留花纹和眼睛颜色，再转成 3MF。”多图可分别指定主体、构图和风格；只要求成品像素 PNG 时，也先执行 Perfect Pixel，再验收整理后的逻辑图和放大预览；明确只要生图原件时才跳过整理。照片辅助生成会产生新的像素画；要求原照片直接转换且不重画时，应使用高保真流程。通用版先用 `tools/refine_pixel.py --png-only --binarize-alpha` 整理透明源图，再正式验收；需要抠图时显式使用 `isnet-general-use`。验收通过的网格直接交给 `tools/lumina_batch.py` 导出两个尺寸，不套用动漫版原图的 60–85 网格门槛，也不强制缩放到 24×24。动漫动作类任务的案例参考图位于 `examples/reference-action-interaction.png`。

## WorkBuddy 通用版下载

- [Skill 与 PDF 整合包](dist/general-pixel-art-to-3mf-workbuddy-bundle.zip)
- [可导入的 Skill ZIP](dist/general-pixel-art-to-3mf-workbuddy.zip)
- [中文 PDF 使用说明](dist/general-pixel-art-to-3mf-workbuddy-guide.pdf)

WorkBuddy 版固定生成纯白、不透明背景；需要时在本地移除背景，先 Perfect Pixel，后正式验收，再导出两个尺寸的 3MF。默认像素风格参考为已整理的柯基。Skill 包需配合已经部署的 Pixel3MF / Lumina 项目使用，不包含 Python 环境或模型权重。

宿主适配规则在 `workbuddy/general-host-adapter.md`，生成后的 Skill 位于 `workbuddy/skills/general-pixel-art-to-3mf/`。运行 `tools/build_general_workbuddy_skill.py` 重建 Skill ZIP；`tools/build_general_workbuddy_guide.py` 使用 ReportLab / pypdf 生成 PDF（当前字体路径适用于 macOS）。完整 WorkBuddy 运行适配保存在 `codex/workbuddy-migration` 分支。

## 环境准备

整个项目只使用根目录下的 `.venv`，依赖由 `uv` 管理：

```bash
cd /Users/aurxs/Program/pixel3mf
uv venv .venv
source .venv/bin/activate
uv pip install -r Lumina-Layers/requirements.txt
uv pip install -r requirements-pixel3mf.txt
```

若默认 uv 缓存目录不可写，可把缓存留在项目内：

```bash
UV_CACHE_DIR=.uv-cache uv pip install -r Lumina-Layers/requirements.txt
UV_CACHE_DIR=.uv-cache uv pip install -r requirements-pixel3mf.txt
```

## 最小运行示例

```bash
.venv/bin/python tools/run_pipeline.py \
  --source-image /absolute/path/to/character.png \
  --character-name "Frieren"
```

可选参数：

- `--reference-image`：只记录到 manifest，供后续追溯。
- `--official-character-research-status completed|not_applicable|unknown`：官方角色研究状态；可识别角色应使用 `completed`，原创主体或直接转换使用 `not_applicable`。
- `--official-character-research-path`：已有 `00_official_character_research.md` 的路径；状态为 `completed` 时必填，脚本会把它复制到本次 run 文件夹。
- `--official-character-source URL`：官方来源 URL，可重复传入；状态为 `completed` 时至少传入一个。
- `--output-root`：输出根目录，默认 `output`。
- `--background-method auto|rembg|white`：`auto` 与兼容别名 `rembg` 使用 IS-Net；`white` 仅使用保守纯色背景清理。
- `--background-model auto|isnet-anime|isnet-general-use`：默认动漫模型；自动模式发现封闭的背景同色组件时，串行调用通用模型复核眼白、高光与真实背景孔洞。
- `--segmentation-device cpu`：兼容参数，仅接受 `cpu`；分割模型不会启用 CoreML、MPS、GPU 或 ANE。
- `--segmentation-memory-limit-gb`：语义模型子进程 RSS 硬上限，默认 `8`；目标峰值低于 `6 GiB`，结果写入 manifest。
- `--working-padding-cells`：逻辑清理使用的临时透明边距，默认每边 `2` 格；导出前全部裁除。
- `--alpha-policy auto|preserve|repair`：默认 `auto`。无有效 Alpha 的白底图沿用完整语义抠图；二值透明图进入双模型保守修补；`preserve` 原样保留 Alpha 并跳过模型；`repair` 强制要求二值透明源图。
- `--mask-override`：提供与源图同尺寸的二值遮罩，跳过模型判断。
- `--allow-ambiguous-mask`：显式接受仍有歧义的背景同色组件；默认停止在 Lumina 之前。
- `--api-url`：Lumina API 地址，默认 `http://127.0.0.1:8000`。若没有服务，脚本会自动启动并在结束后关闭；已有服务会直接复用。
- `--square-output`：可选兼容模式；只添加完整透明逻辑行列来补方。默认保留 Perfect Pixel 的真实矩形网格。

首次使用某个 IS-Net 时会将 ONNX 权重下载到项目 `.cache/rembg/`。推理固定使用 ONNX Runtime `CPUExecutionProvider`，不会探测或注册 CoreML、MPS、GPU 或 ANE。整个流程只使用 `isnet-anime` 与 `isnet-general-use` 的 ONNX 模型，不加载 BiRefNet 或 PyTorch。已有二值 Alpha 默认只审计原本不透明的内部背景孔洞：原透明区域不可变，两个模型一致才提出删除，原轮廓外沿一格受保护；不会把透明像素中隐藏的黑色 RGB 当背景色。纯色背景可显式使用 `--background-method white` 跳过模型。

## 配合 Codex image generation

先在 Codex 中生成图片并保存到本地，再运行上面的总入口。推荐提示词风格：

> 生成单个指定角色的自然上半身像，主体居中，正面或清晰的三分之四视角；画面只到上胸，不向胸部以下延伸；不要对手、手臂或关节施加特殊限制，姿势保持自然。严格按 `24×24` 逻辑像素画设计：使用明显的大方块、阶梯状外轮廓、约 1 个逻辑像素宽的深色描边和很少的内部细节；脸部只保留最关键的眼睛、嘴和发型特征；使用约 8–12 种大面积离散颜色，其中头发可有 3–4 个青绿色阶、肤色 2–3 个色阶，并保留少量深蓝紫和粉色点缀以展示叠色。禁止细碎发丝、纹理、抖色、连续渐变、抗锯齿、柔边和高精插画式高光；不要文字，不要其他角色；背景必须是完全均匀的纯白色，整张 PNG 的每个像素都必须为 Alpha 255；禁止透明、半透明、棋盘格、阴影、渐变或背景纹理。若生成器输出高分辨率位图，它必须看起来像 `24×24` 逻辑图的最近邻放大，而不是增加更多逻辑细节。

生成后先确认它是纯白背景且完全不透明；生图结果出现任何透明或半透明像素时直接重新生成。此限制只针对生成结果，不影响用户直接提交的二值透明 PNG。之后用 Perfect Pixel 自动检测实际网格并进行源图预检。轻微模糊、抗锯齿、整格色阶和相近颜色只记为可恢复警告；最终是否通过由 Pixel Fine 后的稳定网格、二值 Alpha 和语义孔洞检查决定。后处理不强制缩放到 24×24 或 75×75。

生成结果不必在 Python 中模拟 image generation，只需把生成文件的绝对路径传给 `--source-image`。

## Lumina 动态尺寸与固定默认值

脚本会从当前 Lumina 的 `/api/lut/list` 查询 LUT，而不是猜显示名称。当前目标文件是：

`Bambulab&PLA&4色&RYBW&红-蓝-黄-白.npy`

尺寸规则：

- 最终紧裁的 `04_pixel_perfect.png`（`export_grid`）是唯一尺寸依据，不使用原始分辨率、语义遮罩、临时工作边距或固定 `75 mm`
- Lumina 生成阶段的像素单元必须为 `0.42 mm`；每次都从同一逻辑网格导出 `2×2` 与 `3×3` 两个版本
- `2×2` 版本保持原始尺寸，逻辑像素边长为 `0.84 mm`
- `3×3` 版本先按 `1.26 mm` 逻辑像素边长生成精确 Lumina 栅格，再对最终 3MF 的 X/Y 顶点统一乘以 `43/42`（`102.380952%`）；最终等效 Lumina cell 为 `0.43 mm`、逻辑像素边长为 `1.29 mm`，Z 不变
- 例如 `80×79` 的 `3×3` 版本先用 `100.80×99.54 mm` 生成内部 `240×237` 网格，最终 3MF 的物理画布为 `103.20×101.91 mm`；`2×2` 仍为 `67.20×66.36 mm`（内部 `160×158` 网格）
- 尺寸使用十进制定点数生成，并在调用前分别模拟 Lumina 的取整公式；任一版本无法证明精确整数映射时直接失败
- 运行时核对本地 Lumina 的 `PrinterConfig.NOZZLE_WIDTH`；不是 `0.42 mm` 时停止转换
- 不能直接把 `1.29 mm` 对应的总宽度传给 Lumina，否则 `int(target_width_mm / 0.42)` 会改变栅格列数；XY 补偿只发生在 Lumina 已完成颜色堆叠和 3MF 生成之后
- 生图提示词默认要求 `24×24` 逻辑像素风格；`60–85` 仅约束未处理源图的自动检测结果，不对临时 padding 或紧裁后的导出网格重复应用

动态尺寸通过 Lumina 已有的浮点 API/Core 参数传入，不修改 Lumina-Layers 源码。其 GUI 宽高滑块的整数步长不影响本项目的自动流水线。

其余默认值：

- 生成 3MF 前先调用 Lumina 生成 2D 预览，并保留 PNG 产物
- 背板 `1.2 mm`
- `Double-sided`
- 不启用 loop（Lumina batch worker 固定为 `add_loop=False`）
- LUT 实际检测出的 `color_mode`，当前为 `RYBW`
- `modeling_mode=pixel`
- `quantize_colors=256`
- 高级设置里的色相保护 `hue_weight=0.6`
- Lumina 内置孤立像素清理开启
- 优先调用 `/api/convert/batch`，即使只有一张图
- `07_lumina_batch_result_*.zip` 原样保留 Lumina 返回的 3MF 及项目配置；只对已解压并命名的 `08_*.3mf` 成品做幂等配置规范化
- 最终 3MF 直接引用官方 `Bambu Lab A1 mini 0.4 nozzle`、`0.08mm Extra Fine @BBL A1M` 和 `Bambu PLA Basic @BBL A1M` ID；参数结构来自同版本官方项目，机器 G-code、热床/喷嘴温度、速度、加速度和 PLA 流量保持官方值
- Arachne、线宽、单层高度、填充和料塔等改动写成官方 0.08 mm 工艺上的项目级覆盖，不创建新的机器、工艺或耗材 preset；Bambu Studio 可逐项显示并撤回这些改动
- `different_settings_to_system` 按 Bambu Studio 官方项目结构写成 `工艺 + N 个耗材 + 机器` 共 `N+2` 项；只在首项声明工艺改动键，其余项保持空白，确保加载时应用工艺覆盖且不修改官方机型/耗材
- 对基线固定覆盖：`0.08 mm` 首层，相关线宽全部 `0.42 mm`，Arachne，1 圈墙，首层仅单层墙，顶/底壳 0 层，100% `zig-zag` 填充且方向 `0°`，关闭狭窄内部实心填充识别，关闭支撑，自动边缘宽 `5 mm`
- 开启单喷头多材料和擦料塔；塔宽 `170 mm`，擦料塔 brim 宽 `1 mm`，位置 `X=5 mm, Y=160 mm`（A1 mini 打印板上方），关闭擦料塔斜肋外墙；模型自身仍使用自动边缘宽 `5 mm`
- 只替换 `Metadata/project_settings.config`；仅从 Lumina 保留动态颜色、颜色/挤出机映射及冲刷数据，模型几何保持不变。将 H2D 双喷嘴存储的两套冲刷表规范化为 A1 mini 所需的单套 `N×N` 表，并保留原始第一套表的全部数值
- `3×3` 的补偿会先以共同中心烘焙到所有颜色零件的 X/Y 顶点，再整体平移以保持原始左下角位置，避免放大后产生负坐标；三角拓扑、颜色/挤出机映射、Z 坐标和装配关系保持不变，并在 3MF 内写入幂等标记，防止重复放大
- `07_lumina_batch_result_3x3.zip` 保留 Lumina 返回的未补偿原件；`08_<角色名>_3x3.3mf` 是可直接以 `100%` 导入切片器的补偿后成品

## 输出目录

```text
output/<timestamp>_<slug>/
├── 01_source.png
├── 02_semantic_mask.png
├── 02_mask_review_overlay.png
├── 02_mask_components.json
├── 02_bg_removed.png
├── 03_working_grid.png
├── 03_working_grid_preview_8x.png
├── 03_source_alpha_working_grid.png  # 仅透明源图 repair 路径
├── 04_pixel_perfect.png
├── 05_pixel_preview_8x.png
├── 06_lumina_2d_preview_2x2.png
├── 06_lumina_2d_preview_3x3.png
├── 07_lumina_batch_result_2x2.zip
├── 07_lumina_batch_result_3x3.zip
├── 08_<角色名>_2x2.3mf
├── 08_<角色名>_3x3.3mf
├── lumina_api.log          # 仅在脚本自行启动 API 时出现
└── manifest.json
```

`manifest.json` 在流程开始时就创建；成功或异常退出时都会更新。两个最终 3MF 会按 `--character-name` 命名，例如 `08_初音未来_2x2.3mf` 与 `08_初音未来_3x3.3mf`。manifest 顶层记录 `source_grid`、`working_grid` 与 `export_grid`，并按 `2x2` / `3x3` 记录所有文件路径、精确尺寸计划、Lumina 参数、预览、归档、XY 补偿、A1 mini 配置规范化的前后哈希与最终 3MF；模型条目还记录实际 provider、回退原因、耗时、峰值 RSS 与内存上限。歧义阻断时也会保留组件统计、标记预览、状态和错误堆栈。

## 独立工具

- `tools/semantic_segment.py`：在受超时和 RSS 约束的独立 CPU 子进程中串行运行两个 IS-Net。
- `tools/remove_background.py`：按 Alpha 策略生成语义置信度，或安全保留/修补已有二值 Alpha；始终保留原始 RGB。
- `tools/prepare_square_canvas.py`：仅保留旧版比例 padding 的独立工具兼容接口；总流水线不再调用。
- `tools/refine_pixel.py`：先预检原图 `60–85` 网格，再验证语义遮罩后的同网格采样，并产生带临时逻辑边距的工作网格。
- `tools/cleanup_pixel.py`：按输入路由清理封闭背景组件；透明源图禁用 RGB 颜色键和孤立像素删除，并保护原 Alpha 轮廓；最后将 Alpha 二值化、保存歧义诊断并紧裁出唯一导出网格。
- `tools/lumina_batch.py`：按指定的每逻辑像素单元数生成并校验精确动态尺寸；总流程会分别用 `2` 和 `3` 调用它，生成两套 2D 预览、原始 ZIP 与已规范化的成品 3MF。API 不能启动，或当前 checkout 的 batch worker 因核心返回值版本差异失败时，会使用对应版本的相同动态尺寸调用 Lumina 核心、自行打包 ZIP，并在 manifest 记录 `batch_error`。
- `tools/three_mf_xy_scale.py`：对已有 `3×3` 3MF 进行幂等的 XY `43/42` 补偿；统一缩放所有颜色零件、保持中心和 Z，不依赖切片器手动缩放。
- `tools/three_mf_a1mini_profile.py`：对已有 Lumina 3MF 幂等套用固定的 A1 mini 机器/工艺/耗材配置；支持 `--output` 写入新文件，不修改输入原件。固定快照位于 `profiles/bambu_a1mini_0.4_0.08_extra_fine_pixel3mf.json`。
- `tools/run_pipeline.py`：总入口和 manifest 生命周期管理。

XY 补偿和 A1 mini 配置规范化都只使用 Python 标准库处理 3MF，运行时不调用也不要求安装 Bambu Studio。Bambu Studio 仅用于开发时的额外兼容性验收；没有安装切片器的机器仍可正常运行流水线。

每个工具都可用 `--help` 查看独立调用方法。例如只检查像素整理：

```bash
.venv/bin/python tools/refine_pixel.py \
  output/example/02_bg_removed.png \
  output/example/04_pixel_perfect.png \
  output/example/05_pixel_preview_8x.png
```

对旧的 `3×3` 成品补做 XY 补偿：

```bash
.venv/bin/python tools/three_mf_xy_scale.py \
  output/example/08_character_3x3.3mf \
  --output output/example/08_character_3x3_scaled.3mf
```

对旧的 Lumina 3MF 生成新的 A1 mini 成品（输入保持不变）：

```bash
.venv/bin/python tools/three_mf_a1mini_profile.py \
  output/example/raw.3mf \
  --output output/example/a1mini.3mf
```

## 排查

- 背景移除不理想：先查看 `02_semantic_mask.png`、`02_mask_review_overlay.png` 与 `02_mask_components.json`；已抠干净的二值透明图可用 `--alpha-policy preserve`，半抠图默认用 `auto` 或显式 `repair`，也可提供权威的 `--mask-override`。纯色浅背景可显式使用 `--background-method white`。
- Perfect Pixel 检测失败：重新生成更清晰的 24×24 大块像素源图；流水线不会用固定网格硬压或插值挽救。
- Lumina 失败：查看运行目录内 `lumina_api.log` 和 manifest 的 `error`；确认 8000 端口没有被无关服务占用。
- 最终矩形尺寸异常：检查 `03_working_grid.png`、`04_pixel_perfect.png` 和 manifest 的 `source_grid` / `working_grid` / `export_grid`；临时边距不得出现在尺寸计划中。
- 最终 3MF 已内置 A1 mini、Arachne、`0.42 mm` 线宽和其余固定参数；在 Bambu Studio 中保持模型 `100%` 缩放，不要再次把新的 `_3x3.3mf` 放大到 `102.38%`。
