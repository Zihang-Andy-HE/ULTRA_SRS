# ULTRA_SRS 0.3

**Command-line SRS processing: denoise → lipid-to-protein prediction → virtual H&E staining.**

The core workflow consists of three independent, auditable commands: `ultra denoise`, `ultra lipid2protein`, and `ultra virtual-stain`. Each stage writes its outputs and provenance for the next stage. CPU and NVIDIA CUDA execution are supported. **Studio, the desktop launcher, the volume viewer, and research scoring are optional extensions.**

Original ULTRA methods, architectures, and pretrained models are the work of **Zhijie Liu and colleagues**. This repository provides inference integration, fixed numerical contracts, calibration, portability, and reproducibility tools. See [Attribution](#attribution) for the original paper and software.

## Example data: G5.tif

**[Download G5.tif from Google Drive](https://drive.google.com/file/d/1bSHDp2jbAhEbBvFMEuqtOOzOPVI2vrYq/view?usp=drive_link)**

The shared example is the current **150-plane G5 dataset**. Save the downloaded file as `G5.tif` in the repository root. Its metadata is provided in [examples/metadata.json](examples/metadata.json).

| Property | Value |
|---|---|
| Shape / axes | 150 × 1024 × 1024 / ZYX |
| Storage / native intensity | uint16 / 12-bit, 0–4095 |
| Voxel spacing (Z, Y, X) | Approximately 1 × 0.4143204 × 0.4143204 µm |
| File plane ordinals | 1–150 |
| Relative Z coordinates | 0–149 µm from the first file plane |

Data are shared separately from the source repository. See [the three-command workflow](#core-workflow-three-commands) to process the shared G5 data and [data documentation](docs/data.md) for metadata interpretation.

## Install

Use Python 3.10 or 3.11. From a terminal:

```bash
git clone https://github.com/Zihang-Andy-HE/ULTRA_SRS.git
cd ULTRA_SRS
python -m venv .venv
```

Activate the environment on Linux/macOS with `source .venv/bin/activate`, or in Windows PowerShell with `.\.venv\Scripts\Activate.ps1`. Then install the core package and prepare its working directory:

```bash
python -m pip install -e .
ultra-setup --out work
```

`ultra-setup` downloads the three fixed tensor-only checkpoints, verifies SHA256, and copies the configurations and references into `work`. For offline setup, use `ultra-setup --out work --weights-dir CHECKPOINT_DIRECTORY`. Weights and tissue images are distributed separately from Git source. Use a fresh output directory for setup when changing configurations; modified configurations are not overwritten.

PyTorch 2.5.1 is pinned. Install a compatible CUDA build when using NVIDIA GPUs. All three commands accept `--device auto` (the default), `--device cpu`, or `--device cuda:0`; `auto` selects CUDA if available, otherwise CPU. CPU execution can be slow on full volumes.

## Core workflow: three commands

Run these commands from the repository root after downloading `G5.tif` and preparing `work` with `ultra-setup`. The included metadata and configuration support the current 150-plane input with the explicit **native-exploratory** profile. No Studio GUI is needed.

```bash
# 1. Denoise three selected full-resolution file planes.
ultra denoise --input G5.tif --metadata examples/metadata.json --config work/configs/ultra.yaml --out results/01_denoise --planes 1,75,150

# 2. Predict protein from the completed denoising stage.
ultra lipid2protein --from results/01_denoise --out results/02_lipid2protein

# 3. Calibrate full-plane RGB and generate virtual H&E.
ultra virtual-stain --from results/02_lipid2protein --out results/03_virtual_stain
```

Use `--planes all` in the first command to process all 150 planes, or an inclusive range such as `--planes 1:10`. The next stages inherit the selected planes and their coordinates automatically. If `--planes` is omitted, all input planes are selected.

| Command | Main output | Role |
|---|---|---|
| `ultra denoise` | `01_denoise/lipid_denoised.ome.tif` | Denoise the measured lipid signal with explicit fixed parameters |
| `ultra lipid2protein` | `02_lipid2protein/protein_predicted.ome.tif` | Predict protein and stitch full planes |
| `ultra virtual-stain` | `03_virtual_stain/virtual_HE.ome.tif` | Apply pooled V3 calibration and virtual staining |

Stage directories contain configuration snapshots, metadata, checksummed manifests, QC metrics, previews, and logs. Virtual staining also saves `rgb_input.ome.tif`, calibration parameters, orthogonal previews, and `report.html`. Protein and H&E are model predictions.

### Input metadata and exploratory parameters

The single [metadata file](examples/metadata.json) records 150 × 1024 × 1024 uint16 data with native range 0–4095. File plane ordinals are 1–150; Z coordinates are 0–149 µm relative to the first file plane. Original source IDs may remain unknown: the current workflow uses file coordinates directly. Unknown absolute tissue depth, Raman band, and offset correction history remain documented.

The configuration in `work/configs/ultra.yaml` uses a fixed denoising timestep **t=10**, gain **65535/4095**, and algorithmic offset **0**. These are exploratory processing parameters, not a measured depth-dependent policy or dark-current correction. Edit `denoise.t` before starting a new run to select another timestep in 0–999.

V3 calibration is pooled over all processed full planes by default (`calibration.fit_file_planes: "all"`) and remains fixed across the output stack. To fit a subset, set an explicit list of file plane ordinals present in the run before denoising. Dense tiling uses stride 64 for protein prediction and 32 for virtual staining. No model is retrained. See [data documentation](docs/data.md) for metadata field meanings.

### Resume and quality control

Add `--resume` to the identical stage command after interruption:

```bash
ultra denoise --input G5.tif --metadata examples/metadata.json --config work/configs/ultra.yaml --out results/01_denoise --planes 1,75,150 --resume
```

Inputs, selected planes, configuration, model hashes, code, device, and batch size must match the stored run identity. Cached planes and completed files are verified by checksum. Resume an incomplete upstream stage before running the next command. QC warnings remain in the manifests; invalid inputs and calculation errors fail explicitly.

### Optional manual display calibration

Pooled fixed V3 calibration is the default. To inspect and adjust display ranges/gamma after lipid-to-protein prediction:

```bash
ultra-preview --from results/02_lipid2protein --port 8765
```

Open `http://127.0.0.1:8765`, adjust L and D=max(P−L,0), and save the parameter JSON. Replay the saved parameters with:

```bash
ultra virtual-stain --from results/02_lipid2protein --out results/03_manual --manual-params results/manual_rgb.json
```

The preview listens on localhost and shares the batch conversion function. When using a remote compute host, forward the port with `ssh -N -L 8765:127.0.0.1:8765 USER@HOST`.

## Optional: Studio and desktop tools

The core three-command pipeline does not require Studio or its GUI. The following commands are optional alternatives and utilities; examples below run from the repository root with the environment activated.

### Inspect data

```bash
ultra-studio doctor --out environment.json
ultra-studio inspect --input INPUT.tif --out inspection.json
```

Inspection reports TIFF dimensions, intensity range, spacing evidence, and missing source-slice mapping. The exploratory workflow uses the file plane coordinates and does not infer unknown acquisition history.

### Alternative processing profiles

| Profile | Purpose | Contract |
|---|---|---|
| `studio` | Replay the archived Studio numerical workflow | Original epoch-100 denoiser, mean equalization, 65535 normalization, file-index depth schedule, eta=1, and SRH formula; at most 200 planes |
| `native-exploratory` | Explicit transfer to a 12-bit acquisition | SRS weights, fixed user-selected denoising t (default 10), gain=65535/4095, and V3 fitted to selected full planes; same fixed denoising policy as the core CLI; tiling strides can differ |

For the `studio` profile, download/extract the [original Studio archive](https://doi.org/10.5281/zenodo.18323493), then register its assets:

```bash
ultra-studio register-studio --source "Ultra 3D Studio" --out studio_assets.json
ultra-studio run --input INPUT.tif --out results/studio --profile studio --assets studio_assets.json --planes 1 --device auto
```

`--inference-only` permits asset registration without the optional classifier weights. Registration records SHA256 identities; archive authenticity must be established separately. `tools/fetch_studio_assets.py` provides resumable archive downloads.

For exploratory processing using the SRS checkpoints installed by `ultra-setup`:

```bash
ultra-studio run --input INPUT.tif --out results/native --profile native-exploratory --weights work/models --planes 1 --device auto
```

Use `--planes all`, an inclusive range such as `1:10`, or increasing comma-separated file ordinals. Both profiles default to stride 480 for protein and H&E tiling. **This changes numerical results relative to the core pipeline's dense strides of 64 and 32.** Set `--protein-stride 64 --he-stride 32` to match the core tiling settings when using `native-exploratory`. No model is retrained.

Studio runs export intermediate OME-TIFFs, calibration, metrics, checksums, thumbnails, and `report.html`. Add `--resume` only with an identical run identity. Unknown physical Z spacing is omitted; sparse plane positions are preserved.

### Desktop launcher, 3D viewer, and research scoring

```bash
ultra-studio gui

# Optional napari volume viewer:
python -m pip install -e ".[viewer]"
ultra-studio view --input results/native/04_virtual_HE.ome.tif
```

The GUI requires Python with Tk support. Windows users can also run `launch_windows.ps1`, which uses the repository's `.venv` by default or accepts `-Python` for another environment. Choose input/output paths in the interface. The optional `run_G5_pilot.ps1` helper requires explicit `-InputTiff` and `-OutputDirectory` arguments and accepts `-Planes`; it assumes no personal directory layout.

The viewer rejects nonuniform sparse Z selections for physical volume rendering. Without known physical spacing it uses voxel coordinates.

```bash
ultra-studio score --input HE_at_5um.ome.tif --assets studio_assets.json --out results/score --tumor glioblastoma --z-spacing 5
```

The original `glioblastoma`, `astrocytoma`, and `oligodendroglioma` classifiers produce overlapping-window binary probability maps for research. They require at least 10 RGB planes at verified 5 µm Z spacing and 120 × 120 XY pixels. Prepare and record any required subsampling; never relabel metadata to imply a different spacing. Scoring uses `eval()` and an explicit softmax dimension, intentionally correcting the original train-mode BatchNorm behavior. It does not provide validated diagnosis or cell segmentation.

## Attribution

Original methods and pretrained models: [Zhijie Liu et al., Ultrarapid-Deep-3D-Histology](https://github.com/Zhijie-Liu/Ultrarapid-Deep-3D-Histology) and [Ultra 3D Studio, DOI 10.5281/zenodo.18323493](https://doi.org/10.5281/zenodo.18323493).

> Liu, Z., Li, Y., Chen, L., Wei, M., Wei, M., Sun, Y., Wang, T., Cheng, H., Liu, X., Ji, M., and Shi, L. (2026). *Ultrarapid deep 3D histology enables intraoperative mapping of glioma infiltration*. Cell 189(20), 6543–6560.e8. https://doi.org/10.1016/j.cell.2026.07.026

The integration builds on ULTRA_SRS commit `98ca5078c6f8c39b41da1910b7ac7981894166c7`, including its tensor-only checkpoints, inference adapters, pooled V3 calibration, manual preview, and stage manifests. No original-author endorsement or improved diagnostic accuracy is claimed.

Preserve [CITATION.cff](CITATION.cff), [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), and source attribution in derivative distributions. The Zenodo deposit lists CC BY 4.0; this does not assign a blanket license to separate repositories, weights, or dependencies.
