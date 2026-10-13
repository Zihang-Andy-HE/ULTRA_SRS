# Attribution and terms

## 0.3 local engineering adaptation / original-author credit

The original ULTRA concept, diffusion denoising, lipid-to-protein prediction, virtual histology and classifier models belong to Zhijie Liu and colleagues. Primary source: [Ultrarapid-Deep-3D-Histology](https://github.com/Zhijie-Liu/Ultrarapid-Deep-3D-Histology). Software deposit: [Zenodo 18323493, DOI 10.5281/zenodo.18323493](https://doi.org/10.5281/zenodo.18323493), version ULTRA_3D (2026-01-21). The linked Git tag resolves to `bd16bf31035c4ea9acfb31dd8dbceb64821c4051`; the inspected current main resolves to `e571c7f4e7dd3cf759d31d98c77c2a091213c987`. The Studio ZIP in that deposit is a separate artifact from the GitHub source ZIP.

Paper: Liu Z, Li Y, Chen L, Wei M, Wei M, Sun Y, Wang T, Cheng H, Liu X, Ji M, Shi L. *Ultrarapid deep 3D histology enables intraoperative mapping of glioma infiltration.* Cell (2026), 189(20):6543–6560.e8. DOI [10.1016/j.cell.2026.07.026](https://doi.org/10.1016/j.cell.2026.07.026).

The Zenodo API metadata labels its deposit **CC BY 4.0**. Preserve author credit, record link and modification notices when reusing that deposit. The absence of a standalone GitHub LICENSE is a separate observation; this document does not assert that all repositories, separately distributed weights or dependencies share a blanket license.

Added derivative components:

| Component | Original source | Local modification |
|---|---|---|
| `studio_algorithms.py` | Studio `function_preprocess.py`, `function_denoise.py`, `function_protein_prediction.py`, `function_SRH_merge.py`, `function_HE_generation.py` | Callable CPU/CUDA adapters, explicit profiles, input validation, optional batch/stride, safe preprocessing helper; Studio replay preserves original default arithmetic |
| `vendor/score_model.py` | Studio `unet3d_12g/unet3d.py` | Removed import-time device initialization; retained original header credit to Amir Aghdam and 3D U-Net paper |
| `scoring.py` | Studio `function_score.py` and GUI smoothing | Explicit eval mode and softmax axis, protocol checks, float probability export and provenance |
| Existing L2P/HE architectures | Original-author `networks.py` / `model.py` via ULTRA_SRS | Existing attribution retained; no new training |

Zihang-Andy-HE/ULTRA_SRS commit `98ca5078c6f8c39b41da1910b7ac7981894166c7` supplies the base package, tensor-only release assets, numerical contracts, calibration implementation and reproducibility machinery. The current work contributes integration, portability, UI, validation and comparison, not authorship of the original scientific models. No original-author endorsement is implied.

## Historical upstream notice (0.2)

ULTRA reuses model architectures and inference methods associated with Zhijie Liu and colleagues. Upstream: https://github.com/Zhijie-Liu/Ultrarapid-Deep-3D-Histology (audited snapshot e571c7f4e7dd3cf759d31d98c77c2a091213c987).

The vendored L2P and virtual-staining architectures retain their source comments. The V3 calibration implementation and inference adapters preserve the evaluated numerical contracts. The reference statistics are unchanged; source locations have been replaced by logical ROI identifiers.

The denoising model is the evaluated learning-rate 5e-5, epoch-400 non-EMA model. L2P uses the original-author epoch-100 generator, not a replacement trained model. Virtual staining uses the evaluated G_A generator. The registry records original and tensor-only checkpoint hashes. Exporting removed optimizer and training state without changing any inference tensor.

No LICENSE/COPYING file was present in the inspected upstream source trees. No new blanket license is assigned here. Retain these attributions and any original notices subsequently supplied by the authors. Dependency packages retain their respective licenses. Software and weight redistribution terms should be documented by the rights holders.
