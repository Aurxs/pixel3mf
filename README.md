# pixel3mf：像素画转叠色 3MF

本项目在本地串联以下步骤：已有图片 → 去背景 → 保持比例的透明画布 → Perfect Pixel 矩形网格整理 → 轻量孤立像素清理 → 精确动态尺寸 → Lumina-Layers batch API → 叠色 3MF。每次运行都会在 `output/<timestamp>_<slug>/` 新建目录并保留中间文件。

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
- `--background-method auto|rembg|white`：默认先用 rembg；失败时自动退回到 8 邻域外部连通的近白背景转透明。内部白色脸部、衣服和配饰默认保留。
- `--api-url`：Lumina API 地址，默认 `http://127.0.0.1:8000`。若没有服务，脚本会自动启动并在结束后关闭；已有服务会直接复用。
- `--square-output`：可选兼容模式；只添加完整透明逻辑行列来补方。默认保留 Perfect Pixel 的真实矩形网格。

第一次使用 rembg 时，它可能需要下载分割模型。对已带正确透明通道的 PNG，脚本会直接保留透明通道；对纯白或近白背景，也可显式使用 `--background-method white`，无需模型。

## 配合 Codex image generation

先在 Codex 中生成图片并保存到本地，再运行上面的总入口。推荐提示词风格：

> 生成单个指定角色的自然上半身像，主体居中，正面或清晰的三分之四视角；画面只到上胸，不向胸部以下延伸；不要对手、手臂或关节施加特殊限制，姿势保持自然。严格按 `24×24` 逻辑像素画设计：使用明显的大方块、阶梯状外轮廓、约 1 个逻辑像素宽的深色描边和很少的内部细节；脸部只保留最关键的眼睛、嘴和发型特征；使用约 8–12 种大面积离散颜色，其中头发可有 3–4 个青绿色阶、肤色 2–3 个色阶，并保留少量深蓝紫和粉色点缀以展示叠色。禁止细碎发丝、纹理、抖色、连续渐变、抗锯齿、柔边和高精插画式高光；不要文字，不要其他角色；背景纯白或透明。若生成器输出高分辨率位图，它必须看起来像 `24×24` 逻辑图的最近邻放大，而不是增加更多逻辑细节。

生成后用 Perfect Pixel 自动检测实际网格并进行流程验收。若仍像精细插画或检测结果超出配置范围，应从头重新生成；后处理不强制缩放到 24×24 或 75×75。

生成结果不必在 Python 中模拟 image generation，只需把生成文件的绝对路径传给 `--source-image`。

## Lumina 动态尺寸与固定默认值

脚本会从当前 Lumina 的 `/api/lut/list` 查询 LUT，而不是猜显示名称。当前目标文件是：

`Bambulab&PLA&4色&RYBW&红-蓝-黄-白.npy`

尺寸规则：

- 最终 `04_pixel_perfect.png` 的矩形逻辑网格是唯一尺寸依据，不使用原始生图分辨率或固定 `75 mm`
- Lumina 像素单元必须为 `0.42 mm`，每个逻辑像素固定映射到 `3×3` 个 Lumina 单元
- 每个逻辑像素边长为 `1.26 mm`；最终 `W×H` 网格对应 `W×1.26 mm × H×1.26 mm`
- 例如 `80×79` 对应 `100.80×99.54 mm` 和 Lumina 内部 `240×237` 网格；奇数边不补方、不割裂
- 尺寸使用十进制定点数生成，并在调用前模拟 Lumina 的取整公式；无法证明精确 `3W×3H` 映射时直接失败
- 运行时核对本地 Lumina 的 `PrinterConfig.NOZZLE_WIDTH`；不是 `0.42 mm` 时停止转换
- 生图提示词默认要求 `24×24` 逻辑像素风格；Perfect Pixel 只接受每轴 `60–85` 的实际网格并保留检测结果，不强制改成 24×24 或 75×75

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
- 保留 Lumina 生成的原始 3MF 项目配置；流水线不改写打印机、层高、首层或 G-code 等切片参数

## 输出目录

```text
output/<timestamp>_<slug>/
├── 01_source.png
├── 02_bg_removed.png
├── 03_canvas_prepared.png
├── 04_pixel_perfect.png
├── 05_pixel_preview_8x.png
├── 06_lumina_2d_preview.png
├── 07_lumina_batch_result.zip
├── 08_<角色名>.3mf
├── lumina_api.log          # 仅在脚本自行启动 API 时出现
└── manifest.json
```

`manifest.json` 在流程开始时就创建；成功或异常退出时都会更新。最终 3MF 会按 `--character-name` 命名，例如 `08_初音未来.3mf`。manifest 记录输入、角色名、所有文件路径、背景策略、Perfect Pixel 检测与最终矩形网格、清理统计、`0.42 mm` 单元、`3×3` 映射、标称与传输尺寸、预期与模拟 Lumina 网格、Lumina 实际 LUT/参数、2D 预览路径和生成方式、最终 3MF、状态和错误堆栈。

## 独立工具

- `tools/remove_background.py`：rembg 主策略与保守的近白背景 fallback；只删除可连通到画布外部的近白区域，并记录清理统计。
- `tools/prepare_square_canvas.py`：按透明区域裁剪、加比例 padding，默认保留矩形画布；仅显式传入 `--square` 时使用兼容的正方形模式。
- `tools/refine_pixel.py`：Perfect Pixel 自动网格检测并保留真实矩形结果，输出最近邻 8 倍预览，不强制目标网格或正方形。仅显式传入 `--square-output` 时添加完整透明逻辑行列。检测失败时要求回到生图阶段重生。
- `tools/cleanup_pixel.py`：删除孤立前景像素，并在逻辑网格上清理最多两个单元的外轮廓白噪点；内部、较大或有疑义的白色区域会被保留并记录，流水线继续生成，不会中途要求复查。
- `tools/lumina_batch.py`：从最终矩形网格生成并校验精确 `3×3` 动态尺寸，启动或复用 Lumina API、查询 LUT、先生成并保存 2D 预览，再上传单图 batch、保存 ZIP 并取出唯一 3MF。API 不能启动，或当前 checkout 的 batch worker 因核心返回值版本差异失败时，会使用完全相同的动态尺寸调用 Lumina 核心、自行打包 ZIP，并在 manifest 记录 `batch_error`。
- `tools/run_pipeline.py`：总入口和 manifest 生命周期管理。

每个工具都可用 `--help` 查看独立调用方法。例如只检查像素整理：

```bash
.venv/bin/python tools/refine_pixel.py \
  output/example/03_canvas_prepared.png \
  output/example/04_pixel_perfect.png \
  output/example/05_pixel_preview_8x.png
```

## 排查

- 背景移除不理想：对纯色浅背景先试 `--background-method white`，复杂背景保留 `auto`。
- Perfect Pixel 检测失败：重新生成更清晰的 24×24 大块像素源图；流水线不会用固定网格硬压或插值挽救。
- Lumina 失败：查看运行目录内 `lumina_api.log` 和 manifest 的 `error`；确认 8000 端口没有被无关服务占用。
- 最终矩形尺寸异常：检查 `03_canvas_prepared.png`、`04_pixel_perfect.png` 和 manifest 的 `pixel_size_plan`；默认流程不会补方，预期内部网格必须严格为最终宽高的 3 倍。
- 在 Bambu Studio 中缩放：优先保持 `100%`；若要维持 `0.42 mm` 整数网格，X/Y 使用 `整数 ÷ 3` 的等比例缩放（如 `66.67%`、`133.33%`、`200%`），并保持 Z 不变。
