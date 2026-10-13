# Release validation

Version 0.2.0 was installed from a wheel into a new isolated Python 3.10 Linux environment with the pinned dependencies. `pip check` passed. Fourteen regression tests passed; these unit tests are distinct from real-data acceptance.

Real G5 source slices 49–51 were processed at full 1024 × 1024 XY resolution through all three commands and the optional manual-parameter variant. Denoise and L2P arrays were exactly equal to the previous validated integration. All generator tensors in the exported checkpoints were exactly equal to the selected original checkpoint tensors. Manual RGB replay was exactly equal to the shared conversion function. TIFF readback, physical XY spacing, relative Z coordinates, and completed-stage resume were checked.

For this three-plane installation smoke test, V3 used source slice 49 for fitting. This is not a repeat of the earlier 17-plane strategy comparison. The shallow-only calibration hit a bound, retained as a QC warning. The default release configuration still pools five representative depths; it requires those source slices in the input. Unknown absolute Z origin and measured Raman band remain explicit warnings. See validation.json for measured timings, memory and warnings.

The previous strategy comparison favored pooled fixed parameters because depth smoothing had no clear combined benefit across saturation, bounds, color continuity, structure and downstream appearance. This release exposes only pooled fixed V3. No diagnostic improvement is claimed without matched real H&E ground truth.

Full 998-plane execution, native macOS/Windows inference, arbitrary acquisition calibration and clinical validation were not performed. Example TIFF data are not distributed with source.
