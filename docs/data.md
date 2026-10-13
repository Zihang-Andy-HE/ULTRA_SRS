# Input data and metadata

Download the current 150-plane [G5.tif from Google Drive](https://drive.google.com/file/d/1bSHDp2jbAhEbBvFMEuqtOOzOPVI2vrYq/view?usp=drive_link). The sole public metadata file is [examples/metadata.json](../examples/metadata.json). Tissue images are shared separately; no personal filesystem path is included in Git.

After downloading, compare the TIFF's SHA256 with `input_sha256` in the metadata:

```text
e5f950f1791433f0a255b70bba77d53a9e8fc1dc1669f72725a1d2103da980b5
```

| Field | Meaning for this input |
|---|---|
| `input_file`, `input_sha256` | Logical filename and SHA256 of the inspected TIFF |
| `acquisition_id` | `G5_150_native`, a repository label for this input |
| `shape`, `axes`, `dtype` | 150 × 1024 × 1024, ZYX, uint16 |
| `native_bit_depth`, `native_intensity_max` | 12 bits, 4095; supported by embedded OIR bit-count metadata |
| `observed_intensity_range` | Measured pixel minimum/maximum, 0–4095 |
| `voxel_size_um`, `spacing_evidence` | Z=1 µm and XY approximately 0.4143204 µm, with TIFF/ImageJ/OIR evidence |
| `file_plane_ordinals` | 1-based positions within this file, 1–150 |
| `z_positions_um` | 0–149 µm relative to this file's first plane |
| `source_slices` | Null: original acquisition slice IDs have not been established |
| `z_origin_um`, `measured_band_cm_1`, `offset` | Absolute depth, measured Raman band, and correction history are unconfirmed |

File plane ordinals and acquisition slice IDs are separate coordinate systems. Unknown fields remain null until supported by acquisition records. The core CLI consumes this metadata and uses file coordinates directly. Original source IDs are optional for the current exploratory profile.

The three core commands use the `native-exploratory` profile: fixed denoising timestep t=10 by default, gain=65535/4095, and zero algorithmic offset. These settings are exploratory and do not assert a measured depth-dependent calibration. The configuration acquisition ID must match the metadata. If `input_sha256` is present, the actual TIFF must match it.

Use `ultra denoise --planes 1,75,150` for a pilot, or `--planes all` for the full input. Metadata is checked against the full file before selection. Later stages inherit the selected file ordinals and relative Z positions; no replacement metadata file is needed for a pilot.

The denoising configuration and pooled V3 fit are recorded in every run. `calibration.fit_file_planes` defaults to `"all"` processed planes, or may be an explicit list contained in the selected input. Protein and H&E tiling strides are 64 and 32.
