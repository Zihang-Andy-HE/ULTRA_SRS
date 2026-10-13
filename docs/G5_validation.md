# G5 validation

Validation records distinguish the frozen G5_998 command-line protocol from a separate 150-plane TIFF. Input filenames alone do not establish acquisition identity or original source slice mapping. Test data are not included in this repository.

## Independent input check

Inspected the separately supplied `G5.tif` on 2026-10-13. The [machine-readable inspection](G5_independent_inspection.json) records the input checksum, TIFF-derived spacing evidence, intensity range, and per-plane means without personal filesystem paths.

| Property | Observed value |
|---|---|
| Shape / axes | 150 × 1024 × 1024 / ZYX |
| Storage / range | uint16 / 0–4095 |
| XY spacing | Approximately 0.4143204 µm from ImageJ units and TIFF resolution |
| Z spacing | 1 µm; OIR ZSTACK step, length, and plane count agree |
| Zero-mean planes | None |
| Original source slice mapping | Unknown |
| Default frozen calibration fit | Cannot be established from file ordinals |

Independent checks also passed on file planes 1, 75, and 150: OME-TIFF export/readback preserved every pixel and relative Z positions 0, 74, and 149 µm. A contiguous `PhysicalSizeZ` was correctly omitted for this sparse selection. The two historical subset metadata examples were rejected with `Invalid original slice mapping` when applied unchanged to the full 150-plane input.

This confirms TIFF readability, shape, intensity range, metadata evidence, and sparse export behavior. It does not establish correspondence to the original 998-plane G5 acquisition. The historical three-plane and 17-plane metadata examples cannot describe this 150-plane input unchanged. The single current [metadata example](../examples/metadata.json) instead records this input and leaves original source mapping null. Its SHA256, dimensions, dtype, observed range, file ordinals, relative Z coordinates, and embedded 12-bit OIR record were checked against the supplied TIFF. The frozen input validator explicitly rejects the unknown original source mapping; a regression test also confirms that valid historical metadata remains accepted. No original slice mapping was invented, and no core depth-policy inference or full-volume neural inference was performed on this file.

## Current software checks

All 31 unit/contract tests passed under Python 3.11 with the declared core dependency versions. Dependency compatibility checks passed. The installed help commands for `ultra`, each of its three stages, and `ultra-studio` were also checked against the README examples.

The Windows PowerShell launchers and interactive GUI were not executed in this validation; their changes remove environment-layout assumptions and translate interface text. No neural model architecture, weight, or core numerical contract was changed.

## Reported v0.3 development checks

The v0.3 source package reported 29 passing unit/contract tests, processing of file planes 1, 75, and 150, and an additional ten-plane volume sampled at 5 µm. It reported no full 150-plane neural inference or matched H&E ground truth. The detailed artifacts supporting those earlier claims are not included in this source distribution; these figures are historical reports, not results of the independent input check.

Reported Studio comparison: exact denoise, protein, and RGB arrays; virtual H&E maximum difference 1/255 and MAE 0.009112. The original summary did not specify the MAE scale.

| Model | Reported scope |
|---|---|
| glioblastoma | One 10 × 120 × 120 spatial window at 5 µm Z; finite-probability check |
| astrocytoma | One 10 × 120 × 120 spatial window at 5 µm Z; finite-probability check |
| oligodendroglioma | One 10 × 120 × 120 spatial window at 5 µm Z; finite-probability check |

These classifier checks do not measure diagnostic accuracy.

## Historical core pipeline acceptance

The [0.2 acceptance record](validation.md) and [machine-readable results](validation.json) describe processing genuine G5 source slices 49–51 with the three core commands. They are separate from the 150-plane input check and must not be treated as validation of an unknown acquisition mapping.
