# G5 input checks

The separately supplied 150-plane `G5.tif` was inspected on 2026-10-13. The [machine-readable inspection](G5_independent_inspection.json) records its content checksum, TIFF-derived spacing evidence, range, and per-plane means without personal filesystem paths.

| Property | Observed value |
|---|---|
| Shape / axes | 150 × 1024 × 1024 / ZYX |
| Storage / native range | uint16 / 12-bit, 0–4095 |
| XY spacing | Approximately 0.4143204 µm from ImageJ units and TIFF resolution |
| Z spacing | 1 µm; OIR ZSTACK step, length, and plane count agree |
| Zero-mean planes | None |
| Original acquisition slice IDs | Unknown |

File planes 1, 75, and 150 passed an OME-TIFF export/readback check: every pixel and relative Z positions 0, 74, and 149 µm were preserved. A contiguous `PhysicalSizeZ` was correctly omitted for this sparse selection.

The [metadata example](../examples/metadata.json) was checked against the supplied TIFF for SHA256, dimensions, dtype, intensity range, file ordinals, relative Z coordinates, and the embedded 12-bit OIR record. These checks cover input properties and file I/O. The separate real-model run below covers one plane; no full-volume neural inference or clinical validation was performed.

## Current software checks

All 38 unit/contract tests passed under Python 3.11 with the declared core dependency versions. Dependency compatibility checks passed. The installed help commands for `ultra`, each of its three stages, and `ultra-studio` were also checked against the README examples.

The Windows PowerShell launchers and interactive GUI were not executed in this validation; their changes remove environment-layout assumptions and translate interface text. No neural model architecture or weight was changed. The core commands now use the explicit native-exploratory policy and file-relative coordinates. Tests cover three-stage orchestration with synthetic model adapters, sparse selection, checksum rejection, changed-selection resume rejection, and completed-output integrity.

## Single-plane core inference check

The three actual core commands completed on file plane 75 of the supplied TIFF, at full 1024 × 1024 resolution on CPU with the released model weights. The run used fixed t=10, gain=65535/4095, zero algorithmic offset, protein stride 64, and H&E stride 32. V3 was fitted to the selected full plane. All three completed stages passed `--resume` checksum verification; the manual preview rendered the correct file plane and relative Z=74 µm.

Denoised lipid, predicted protein, calibrated RGB, and virtual H&E were produced. Their manifests retain exploratory-use and calibration warnings. Output identities and the exact source code hash are recorded in [the machine-readable checks](G5_independent_inspection.json). This is a single-plane execution check, not a full 150-plane run or a measurement of diagnostic accuracy.
