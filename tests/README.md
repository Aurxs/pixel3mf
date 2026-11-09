# 测试维护

保留用户可见的核心流程、实际 Bug 的回归，以及会破坏结果或输入文件的关键边界：尺寸和网格、RGB/Alpha 与孔洞、审核后导出、原文件保护、异步任务恢复和重复提交限制。

- 同一行为的输入变体优先用 `subTest` 表格，共用准备步骤；不同失败原因应能单独定位。
- 尺寸类检查使用上下界、典型方形/矩形和已知小数误差案例，避免重复穷举所有组合。
- 提示词检查关注输入传递与状态行为，不逐句锁定文案；样式检查关注成品约束，不反复与历史默认值比较。
- 外部 API、分割模型和 Lumina 转换使用替身；配置解析使用临时样本，不依赖未跟踪的第三方 checkout。
- 新增测试前确认现有用例是否已覆盖同一风险。不要仅为减少数量删除独立的回归保护。

只运行当前改动涉及的测试模块，例如：

```sh
PYTHONPATH=tests .venv/bin/python -m unittest -q test_pixel_sizing test_grid_detection
ruff check tests/test_pixel_sizing.py tests/test_grid_detection.py
```

Windows 使用 `.venv/Scripts/python.exe`，并按所用终端设置 `PYTHONPATH=tests`。
