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

`skills/` 是随本项目一起复制进来的 Codex skill 文件夹，不是压缩包；本项目只保留 `pixel-art-to-3mf-skill`，通用 Codex skills 不随项目分发。生成或转换任务需要使用它时，可直接查看 `skills/pixel-art-to-3mf-skill/SKILL.md`。动作类任务的案例参考图位于 `examples/reference-action-interaction.png`。

## WorkBuddy 适配

`skills/pixel-art-to-3mf-skill` 仍是唯一核心 Skill 来源。项目目录遵循 [WorkBuddy Skills 官方文档](https://cloud.tencent.com/document/product/1831/134516) 的 `.codebuddy/skills/` 约定。以下命令会生成并校验项目级 `.codebuddy/skills/pixel-art-to-3mf/`，同时制作可上传到 WorkBuddy 个人 Skills 的 ZIP：

```bash
.venv/bin/python tools/build_workbuddy_skill.py --package
```

WorkBuddy 生图模板单独保存在 `workbuddy/generation-prompt.md`，与 `workbuddy/source-acceptance.md` 一起覆盖宿主副本的对应 references，CLI 的 `render-prompt` 也读取它。混元原生生图采用明确的 `64×64` 全画布网格和简化造型描述；Codex 核心模板保持不变，源图验收规则也不变。编排模型可选择 `Deepseek-V4.1-Flash`，原生绘图由独立 ImageGen 服务执行，`--model` 应记录真实绘图模型。

项目级 WorkBuddy 说明保存在 `workbuddy/project-instructions.md`，非敏感配置模板保存在 `workbuddy/config.example.json`。把模板复制为仓库根目录的 `.workbuddy.local.json` 后填写私有 COS bucket；该本地配置和 `dist/` 均被 Git 忽略。

WorkBuddy 总入口提供环境检查、任务初始化、隔离提示词渲染、单次生图/候选导入、视觉决定和转换：

```bash
.venv/bin/python tools/workbuddy_pixel3mf.py doctor
.venv/bin/python tools/workbuddy_pixel3mf.py configure-keychain tokenhub
.venv/bin/python tools/workbuddy_pixel3mf.py configure-keychain cos-secret-id
.venv/bin/python tools/workbuddy_pixel3mf.py configure-keychain cos-secret-key
.venv/bin/python tools/workbuddy_pixel3mf.py init-run --help
.venv/bin/python tools/workbuddy_pixel3mf.py generate --help
.venv/bin/python tools/workbuddy_pixel3mf.py render-prompt --help
.venv/bin/python tools/workbuddy_pixel3mf.py import-candidate --help
.venv/bin/python tools/workbuddy_pixel3mf.py resume-generation --help
.venv/bin/python tools/workbuddy_pixel3mf.py cleanup-references --help
.venv/bin/python tools/workbuddy_pixel3mf.py decide --help
.venv/bin/python tools/workbuddy_pixel3mf.py convert --help
```

TokenHub 与 COS 密钥优先从 macOS Keychain 的 `pixel3mf.tokenhub` / `pixel3mf.cos` service 读取；CI 可使用 `PIXEL3MF_TOKENHUB_API_KEY`、`PIXEL3MF_COS_SECRET_ID`、`PIXEL3MF_COS_SECRET_KEY`、`PIXEL3MF_COS_BUCKET` 和 `PIXEL3MF_COS_REGION`。不要把密钥写进 `.workbuddy.local.json`。

WorkBuddy CLI 默认不附带内置风格图，`init-run --no-bundled-style` 可显式声明；仅在需要参考图时使用 `--with-bundled-style`，避免旧粗格参考图把输出拉回低密度或复制参考角色；需要参考图时再显式启用。原生候选导入会保留原始文件和 SHA-256，仅把与整圈近白边框连通、RGB 三通道均不低于 240 且通道差不超过 8 的不透明背景归一到纯白。内部封闭高光、Alpha、图像尺寸和网格均不修改；`background_normalization` 审计信息会进入最终 manifest。网格和构图验收仍然有效。`render-prompt --json` 同时返回隔离提示词和真实原始参考图路径；每个新 run 固定保存当时的模板，后续全局模板更新不会悄悄改变在途任务。

TokenHub 未配置时，可在 WorkBuddy 中用 `render-prompt` 输出的隔离提示词调用默认生图能力，并用 `import-candidate` 登记每张候选。该入口与 TokenHub 共用最多 3 次的硬限制、客观预检和 `decide` 视觉验收；它不是已提交 TokenHub 任务的自动回退。

COS 只作为 TokenHub 拒绝 data URI 时的后备。桶必须保持私有读，预签名 URL 固定 15 分钟，任务结束后由编排器删除对象；`workbuddy/cos-cam-policy.example.json` 给出仅限 `workbuddy-reference/` 前缀上传、读取和删除的子账号策略，`workbuddy/cos-lifecycle.example.json` 给出 1 天生命周期兜底。把示例中的 APPID 与桶名占位符替换后再通过腾讯云控制台应用，不要授予公共读。

原生生图验收后，若为闭合轮廓、纯白背景且内部白色明确是眼白/高光的简单像素图，可用 `convert --background-method white` 保留主体完整外形；需要判断内部背景孔洞时继续使用语义分割。最终必须对照原图检查肩部、外轮廓和底线，不能仅凭 `manifest.status=success` 交付。若语义分割误删主体，保留旧 run，从已验收源图初始化新 direct run，用保守白底模式重导，保留来源链。

分割子进程仅调用 ONNX `session.predict`，设置 `NUMBA_DISABLE_JIT=1` 跳过 rembg 导入时不使用的 PyMatting JIT 缓存探测，避免 WorkBuddy 首次运行触发大量临时文件清理；CPU 推理、RSS 限额及宿主安全检查保持有效。

## 环境准备

整个项目只使用根目录下的 `.venv`，依赖由 `uv` 管理：

```bash
cd /Users/aurxs/Program/pixel3mf_workbuddy
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

> 生成单个指定角色的自然上半身像，主体居中，正面或清晰的三分之四视角；画面只到上胸，不向胸部以下延伸；不要对手、手臂或关节施加特殊限制，姿势保持自然。以 `24×24` 像素画的简化程度和低信息密度作为视觉先验：使用明显的大方块、统一逻辑网格、阶梯状外轮廓、约 1 个逻辑像素宽的深色描边和很少的内部细节；脸部只保留最关键的眼睛、嘴和发型特征；使用约 8–12 种大面积离散颜色，其中头发可有 3–4 个青绿色阶、肤色 2–3 个色阶，并保留少量深蓝紫和粉色点缀以展示叠色。禁止细碎发丝、纹理、抖色、连续渐变、抗锯齿、柔边和高精插画式高光；不要文字，不要其他角色；背景必须是完全均匀的纯白色，整张 PNG 的每个像素都必须为 Alpha 255；禁止透明、半透明、棋盘格、阴影、渐变或背景纹理。若生成器输出高分辨率位图，它必须像同一粗网格的最近邻放大，而不是增加更多逻辑细节。

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
- 生图提示词以 `24×24` 的简化程度作为视觉先验；`60–85` 是未处理源图的权威自动检测范围，不对临时 padding 或紧裁后的导出网格重复应用

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
- 最终 3MF 使用固定的 Bambu Lab A1 mini 0.4 mm 机型与官方 `0.08mm Extra Fine @BBL A1M` 基线；机器 G-code、热床/喷嘴温度、速度、加速度和 PLA 流量来自该基线快照
- 对基线固定覆盖：`0.08 mm` 首层，相关线宽全部 `0.42 mm`，Arachne，1 圈墙，首层仅单层墙，顶/底壳 0 层，100% `zig-zag` 填充且方向 `0°`，关闭狭窄内部实心填充识别，关闭支撑，自动边缘宽 `5 mm`
- 开启单喷头多材料和擦料塔；塔宽 `170 mm`，擦料塔 brim 宽 `1 mm`，位置 `X=5 mm, Y=160 mm`（A1 mini 打印板上方），关闭擦料塔斜肋外墙；模型自身仍使用自动边缘宽 `5 mm`
- 只替换 `Metadata/project_settings.config`；Lumina 动态颜色、颜色/挤出机映射和模型几何保持不变。将 H2D 双喷嘴存储的两套冲刷表规范化为 A1 mini 所需的单套 `N×N` 表，并保留原始第一套表的全部数值
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

## 通用像素画 WorkBuddy 版

- [Skill 与 PDF 整合包](dist/general-pixel-art-to-3mf-workbuddy-bundle.zip)
- [Skill ZIP](dist/general-pixel-art-to-3mf-workbuddy.zip)
- [PDF 使用说明](dist/general-pixel-art-to-3mf-workbuddy-guide.pdf)

使用项目级 `.codebuddy/skills/general-pixel-art-to-3mf/`，与原动漫版分开。生图固定纯白不透明背景，使用处理后的柯基作为像素风格参考；先背景准备和 Perfect Pixel，后正式验收，再直接用 Lumina 导出两份 3MF，不经过原动漫版的 60–85 源图门槛。

`tools/build_general_workbuddy_skill.py` 从 `skills/general-pixel-art-to-3mf` 和 `workbuddy/general-host-adapter.md` 构建发布包；生成后同步项目级 Skill。PDF 构建源是 `tools/build_general_workbuddy_guide.py`。
