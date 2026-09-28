# Attribution and terms

ULTRA reuses model architectures and inference methods associated with Zhijie Liu and colleagues. Upstream: https://github.com/Zhijie-Liu/Ultrarapid-Deep-3D-Histology (audited snapshot e571c7f4e7dd3cf759d31d98c77c2a091213c987).

The vendored L2P and virtual-staining architectures retain their source comments. The V3 calibration implementation and inference adapters preserve the evaluated numerical contracts. The reference statistics are unchanged; source locations have been replaced by logical ROI identifiers.

The denoising model is the evaluated learning-rate 5e-5, epoch-400 non-EMA model. L2P uses the original-author epoch-100 generator, not a replacement trained model. Virtual staining uses the evaluated G_A generator. The registry records original and tensor-only checkpoint hashes. Exporting removed optimizer and training state without changing any inference tensor.

No LICENSE/COPYING file was present in the inspected upstream source trees. No new blanket license is assigned here. Retain these attributions and any original notices subsequently supplied by the authors. Dependency packages retain their respective licenses. Software and weight redistribution terms should be documented by the rights holders.
