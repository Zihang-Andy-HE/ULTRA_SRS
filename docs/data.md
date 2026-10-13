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
| `source_slices` | Null: mapping to the original 998-plane acquisition is unknown |
| `z_origin_um`, `measured_band_cm_1`, `offset` | Absolute depth, measured Raman band, and correction history are unconfirmed |

File plane ordinals are not original acquisition slice IDs. Do not replace `source_slices: null` with 1–150 or rename this acquisition to `G5_998_native` merely to pass validation. The frozen core protocol needs verified original source IDs, applicable acquisition metadata, and calibration fit slices present in the input.

The `native-exploratory` CLI profile can process the TIFF with an explicit transfer policy. It reads the image directly and does not consume this metadata JSON. Its fixed denoising timestep and selected-plane calibration are separate from the frozen core depth policy.

The former metadata examples described 17 selected original slices and a three-slice pilot (49–51). They were not identical. They have been replaced by the actual input description; historical core test metadata is now an internal unit-test fixture. See [validation](G5_validation.md) for observed properties and the limits of the checks.

## Reference configuration for the core CLI

The bundled `configs/ultra.yaml` retains the historical `G5_998_native` numerical contract: uint16 input in 0–4095, 1024 × 1024 XY planes, and verified original slice IDs 1–998. The default pooled V3 fit selects original source slices 49, 239, 499, 801, and 949. For a supported subset, choose representative `calibration.fit_source_slices` that are actually present, before starting denoising.

Those identifiers describe the reference policy, not the shared 150-plane dataset. Updating the data download or its metadata does not recalibrate this policy. The current shared file uses the explicitly exploratory profile documented in the README until applicability of a core acquisition policy is established.
