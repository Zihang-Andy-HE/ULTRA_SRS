# ULTRA_SRS 0.3 — portable research workstation

**Original ULTRA methods, architectures and pretrained models are the work of Zhijie Liu and colleagues, not newly trained models from this upgrade.** Please credit and cite their [Ultrarapid-Deep-3D-Histology repository](https://github.com/Zhijie-Liu/Ultrarapid-Deep-3D-Histology), [Ultra 3D Studio archive, DOI 10.5281/zenodo.18323493](https://doi.org/10.5281/zenodo.18323493), and the paper:

> Liu, Z., Li, Y., Chen, L., Wei, M., Wei, M., Sun, Y., Wang, T., Cheng, H., Liu, X., Ji, M., and Shi, L. (2026). *Ultrarapid deep 3D histology enables intraoperative mapping of glioma infiltration*. Cell 189(20), 6543–6560.e8. https://doi.org/10.1016/j.cell.2026.07.026

This local engineering upgrade builds on [Zihang-Andy-HE/ULTRA_SRS](https://github.com/Zihang-Andy-HE/ULTRA_SRS), commit `98ca5078c6f8c39b41da1910b7ac7981894166c7`. Credit that integration for its tensor-only checkpoints, frozen inference contracts, pooled V3 calibration, manual display preview and checksummed stage manifests. The present changes add Windows/CPU operation, acquisition inspection, a desktop launcher, a Studio-compatible workflow, explicit exploratory transfer, original classifier support and reproducible G5 comparisons. They do **not** establish improved diagnostic accuracy or endorsement by the original authors.

## 中文快速开始

当前交付目录为 `D:\HZH\ULTRA`，代码在 `ULTRA_SRS_upgraded`，环境在 `.venv`。直接启动：

```powershell
cd D:\HZH\ULTRA
.\.venv\Scripts\python.exe -m ultra.studio gui
```

也可运行 `ULTRA_SRS_upgraded\launch_windows.ps1`。界面提供文件选择、数据检查、CPU/GPU 选择、切片选择、进度日志、停止、恢复、结果报告、可选 3D 查看器和三种研究用评分。输出目录必须是新目录；继续同一任务时勾选恢复。层号是 **TIFF 内的 1-based 文件层号**，不是另一份 998 层数据的原始层号。

本次 `G5.tif` 实际是 `150 × 1024 × 1024`、uint16、范围 0–4095。XY 由 ImageJ/TIFF resolution 读取，Z 由相符的 OIR `ZSTACK`、`length z #1`、轴步长和层数读取：约 `1 × 0.4143204 × 0.4143204 µm (Z,Y,X)`。绝对组织深度和与仓库 998 层 G5 的对应关系仍未知。

### Three intentionally separate workflows

| Workflow | Purpose | Important contract |
|---|---|---|
| `ultra denoise / lipid2protein / virtual-stain` | Existing frozen G5_998 pipeline | Requires genuine source slice mapping and acquisition metadata; unchanged numerical formulas |
| `ultra-studio run --profile studio` | Archived Studio numerical workflow on CPU/CUDA | Original epoch-100 denoiser, mean equalization, 65535 normalization, depth schedule, eta=1, SRH formula; seeds are recorded |
| `ultra-studio run --profile native-exploratory` | Explicit transfer of SRS methods to a 12-bit acquisition | SRS weights, fixed user-selected denoise t, gain=65535/4095, pooled V3 fitted to selected full planes; **not** the frozen G5 depth protocol |

Studio uses its original file-index schedule, limited to 200 planes. The new workflow does not pretend this schedule is calibrated to arbitrary physical depths. `native-exploratory` defaults to `t=10`; this is an exploratory setting, not a learned depth policy. It does not retrain any model.

### Installation on another machine

Use Python 3.10 or 3.11. Keep weights separate from source.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
# Optional volume renderer:
.\.venv\Scripts\python.exe -m pip install -e ".[viewer]"
```

On Linux use `.venv/bin/python`. PyTorch 2.5.1 is pinned; install an appropriate CUDA build for GPU use. `auto` chooses CUDA when available, otherwise CPU. CPU was tested locally; GPU memory requirements depend on model and plane size. The previous 24 GiB startup requirement and 20% allocation cap were removed; this does not certify every smaller GPU. CUDA out-of-memory errors remain visible and preserve completed plane caches.

```powershell
python -m ultra.studio doctor --out environment.json
python -m ultra.studio inspect --input G5.tif --out G5_inspection.json
python -m ultra.setup --out work
```

For the archived Studio, download/extract `Ultra 3D Studio.zip` from the linked Zenodo record (or use `tools/fetch_studio_assets.py` for resumable range downloads). Register the original weights:

```powershell
python -m ultra.studio register-studio --source "Ultra 3D Studio" --out studio_assets.json
```

`--inference-only` permits registration before the three classifier weights are available. Registration records local SHA256 identities; it is not a substitute for archive authenticity checking. The supplied acquisition scripts check ZIP CRC and sizes, and SRS releases check their fixed SHA256 registry. See the final report for actual identities.

### Pilot, batch and recovery

```powershell
# Exact archived numerical profile, portable execution:
python -m ultra.studio run --input G5.tif --out results/studio --profile studio --assets studio_assets.json --planes 1,75,150 --device auto

# Explicit exploratory native profile; this is NOT an automatic G5_998 mapping:
python -m ultra.studio run --input G5.tif --out results/native --profile native-exploratory --weights weights_srs --planes 1,75,150 --device auto
```

Use `--planes all` for a full stack, `--planes 1:10` for an inclusive contiguous range, or comma-separated increasing ordinals. Use `--protein-stride 64 --he-stride 32` to select SRS dense overlap. The Studio/new launcher defaults to stride 480 (9 patches per 1024 plane), while the older SRS methods use 81/289 patches. **The fast setting changes numerical results** and must not be advertised as an equivalent optimization. The report measures this tradeoff with identical stage inputs.

Append `--resume` to the **identical** command after interruption. Input bytes, profiles, parameters, model hashes, code and device must match; cached planes and finished files are checksummed. A corrupt plane cache is recomputed. A corrupt completed output is rejected. Run manifests retain warnings and failures. Do not edit a stored identity to force reuse.

Each workflow saves preprocessing, denoised lipid, predicted protein, model-input RGB and virtual H&E as OME-TIFF, calibration JSON, stage metrics, checksums, thumbnails and `report.html`. Protein remains a prediction. For unknown Z spacing the output omits physical Z metadata. Sparse selections retain plane positions and are never silently collapsed into a contiguous physical volume. File-relative coordinates are not absolute tissue depth.

### 3D viewer and research classifier

```powershell
python -m ultra.studio view --input results/native/04_virtual_HE.ome.tif
python -m ultra.studio view --input contiguous_HE.ome.tif --score score/probability.tif
python -m ultra.studio score --input HE_at_5um.ome.tif --assets studio_assets.json --out score --tumor glioblastoma --z-spacing 5
```

`view` opens optional napari with volume rotation, 2D/3D switching, physical scale and optional probability overlay. Nonuniform sparse Z selections are rejected for physical volume rendering; use individual images or a separately documented resampling operation. Without known physical Z the viewer uses voxel coordinates.

Classifier choices are `glioblastoma`, `astrocytoma`, `oligodendroglioma`. These are the original overlapping-window **binary classification probability maps**, not three-way calibrated diagnosis or cell segmentation. The original protocol uses a 10×120×120 patch at 5 µm Z and repeats Z fivefold before its 3D CNN; the upgrade requires that protocol explicitly and checks OME Z coordinates. G5 is 1 µm: use a recorded every-fifth-plane selection, not a false metadata relabel. At least ten correctly spaced planes are required. The upgrade calls `eval()` and explicit softmax dimension, fixing the original train-mode BatchNorm behavior; corrected scoring is therefore intentionally not numerically identical to the original bug. Probability maps are float32; smoothing is applied to float probabilities with the original sigma. No classifier accuracy was assessed on this unlabeled sample.

## What was tested

See `docs/G5_validation.md` and the final report in the parent directory for the actual tested scopes and metrics. The inherited 0.2 GPU reports below describe prior authors' experiments; they are not new validation on this computer. This release does not claim a full 150-plane three-stage run, new training, matched histological ground truth or clinical validation unless explicitly recorded in the report.

## Attribution and distribution

Keep this README, `CITATION.cff`, `THIRD_PARTY_NOTICES.md`, source comments and links with derivative distributions. The Zenodo record lists CC BY 4.0 for its deposit. The inspected GitHub trees have no standalone blanket LICENSE; that fact is recorded separately, and the archive's record-level license is not silently applied to unrelated repositories or dependencies. This upgrade adds no blanket license over third-party code or checkpoints. It makes no claim of original authorship of ULTRA architectures or weights.

---

Historical installation and GPU validation notes are preserved in [docs/upstream_README_0.2.md](docs/upstream_README_0.2.md). They describe the prior release, not the current local validation.
