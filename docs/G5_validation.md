# G5 local validation

Final report: ../../Final_Report.md. Source commit baseline: 98ca5078c6f8c39b41da1910b7ac7981894166c7.

29 unit/contract tests pass; real planes 1,75,150; additional 10-plane 5 um sampled volume. No full 150-plane neural inference or matched H&E ground truth.

Studio parity: denoise/P/RGB exact; H&E max 1/255, MAE 0.009112.

| 模型 | 状态 | 测试范围 |
|---|---|---|
| glioblastoma | complete | 10×120×120、一个空间窗口，5 µm Z；有限概率检查 |
| astrocytoma | complete | 10×120×120、一个空间窗口，5 µm Z；有限概率检查 |
| oligodendroglioma | complete | 10×120×120、一个空间窗口，5 µm Z；有限概率检查 |

See results/final_summary.json in the parent workspace for measured data.
