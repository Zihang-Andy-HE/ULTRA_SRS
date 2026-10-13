# ULTRA (historical v0.2 documentation)

This archived document describes v0.2 behavior. For current installation, device support, and commands, see the [main README](../README.md).

A Linux-first Python package for denoising → lipid-to-protein prediction → virtual staining and 3D orthogonal previews. NVIDIA CUDA is the evaluated inference backend. The optional browser interface can be viewed from Linux, macOS or Windows; computation stays on the Linux host.

## Installation

Clone this repository and use Python 3.10 in an isolated Linux environment:

```bash
git clone https://github.com/Zihang-Andy-HE/ULTRA_SRS.git
cd ULTRA_SRS
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements-lock.txt
pip install .
ultra-setup --out work
cd work
```

`ultra-setup` obtains exactly one fixed tensor-only checkpoint per model, verifies SHA256, and creates the configuration and references. For offline use, provide the previously downloaded checkpoint directory with `--weights-dir`. Large weights are distributed separately from Git source.

## Three commands

Place your input and its metadata in the working directory. Example TIFFs will be supplied later through an external link (see docs/data.md).

```bash
ultra denoise --input INPUT.tif --metadata metadata.json --config configs/ultra.yaml --out results/01_denoise
ultra lipid2protein --from results/01_denoise --out results/02_lipid2protein
ultra virtual-stain --from results/02_lipid2protein --out results/03_virtual_stain
```

The current validated configuration supports the G5 acquisition, 1024 × 1024 planes and original slice IDs 1–998. It is not a universally calibrated protocol for arbitrary acquisitions. The supplied default V3 fit requires source slices 49, 239, 499, 801 and 949 in the input. Set representative fit_source_slices before the first command for a different supported subset; calibration is pooled once and fixed across the stack.

Each stage saves a configuration snapshot, metadata, manifest, TIFF, previews, QC and logs. Add `--resume` to the identical command after interruption; cached planes are checksum verified. Changed inputs, parameters or code cannot reuse an incompatible result. QC warnings are retained without an approval gate; invalid inputs and calculation errors fail.

L2P is stitched into full planes before V3 calibration. RGB is saved before virtual-stain patch inference. Physical spacing is read from metadata, never guessed. Sparse slices retain their original relative Z positions.

## Optional manual display calibration

On the compute host:

```bash
ultra-preview --from results/02_lipid2protein --port 8765
```

On a client computer, forward the port using your own SSH destination:

```bash
ssh -N -L 8765:127.0.0.1:8765 USER@HOST
```

Open http://127.0.0.1:8765 in a browser. The service listens only on localhost. Adjust L and D=max(P−L,0) ranges and gamma, inspect saturation, then save JSON on the compute host. Replay it using:

```bash
ultra virtual-stain --from results/02_lipid2protein --out results/03_manual --manual-params results/manual_rgb.json
```

Preview and batch inference share the conversion function; no per-patch refitting occurs. Standard V3 remains the default.

## Scope and troubleshooting

CUDA startup currently requires at least 24 GiB free and caps this process at 20% of device memory; use a suitable available GPU with `--device cuda:0`. This conservative policy was evaluated on an 80 GiB GPU. CPU is available through `--device cpu`, but runtime is not benchmarked here. macOS/Windows native inference is not validated.

A checksum error means an asset is missing or corrupt: restore the fixed asset, never edit its hash to bypass validation. An incomplete upstream stage must be resumed before continuing. Metadata must describe the actual acquisition; never relabel cropped slices to change the denoising policy.

No matched real H&E ground truth was available. Outputs and proxy metrics do not establish diagnostic improvement. The previous integration was tested on 17 real full planes; a full 998-plane run and model retraining are outside this release's validation scope.

See model_registry.json for checkpoint identities and THIRD_PARTY_NOTICES.md for attribution and unresolved licensing terms.
