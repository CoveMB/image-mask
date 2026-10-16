TEN-PHOTO AUTOMATIC MASK TEST
BiRefNet_dynamic-matting • 11 October 2026

Purpose
A mask-only, out-of-the-box test across ten original DNG photographs. No generative image editing, prompts, hand-painted masks, morphology cleanup, or foreground reconstruction was used. The model chooses the foreground automatically, which can include a supporting leaf or stem.

What the files mean
- reference_renders: full-size unmasked reference renders, 8-bit sRGB PNG. These are matching test references, not RAW-quality masters.
- masks: separate, full-size 16-bit grayscale soft masks. White retains the image, black removes it, and gray partially retains it. Use as a layer mask, aligned exactly with the corresponding reference render. Keep mask pixel values linear; do not apply a color profile or gamma correction to the mask.
- black_composites: full-size 8-bit sRGB PNGs made only by multiplying the reference pixels by the mask.
- previews: reduced-size source and black-composite JPEGs for quick inspection.
- Ten-photo-mask-comparison.jpg: source / mask / result overview.
- manifest.json: exact source hashes, dimensions, crop/orientation, recipe, model revision, inference dimensions and per-photo runtime.
- EVALUATION.txt: photo-by-photo visual findings and limitations.

Resolution and orientation
The nine standard DNGs have a 4080×3072 sensor raster and export in their recorded portrait orientation at 3072×4080. The caterpillar exports at 2974×3950. No additional artistic crop is applied. LibRaw's visible full image is retained; the separate DNG DefaultCropSize is not applied again. These masks align exactly with the supplied reference renders. A different RAW converter or an earlier edit may apply a default border crop, lens correction, rotation or other geometry change. Match that geometry before reusing these masks; matching only the nominal pixel count is not sufficient.

Inference is not native-resolution inference. Each developed photo is reduced proportionally to 1536 pixels high, then edge-padded on the right to a multiple of 32. Standard content is 1157×1536 within an 1184×1536 input; the caterpillar's exact dimensions are in the manifest. Padding is removed from the prediction, and the soft mask is bilinearly projected back to full-size photo coordinates. The larger exported mask does not recover detail the smaller inference missed.

RAW development
All ten photographs use the same explicit LibRaw recipe: AHD demosaicing, an explicit daylight white-balance baseline, sRGB output, gamma (2.4,12.92), brightness multiplier 1, automatic brightness at the 1% threshold, full-size output, and automatic EXIF orientation. No extra sharpening or denoising is added. The DNGs record as-shot white balance as xy coordinates, but this LibRaw path does not expose usable as-shot multipliers; the invalid camera-WB setting was rejected before these final files were produced. The daylight baseline is a test preset, not a final color grade. Development is calculated at 16-bit and rounded to an 8-bit PNG reference for this test package. The DNG originals are unchanged and are not duplicated here. This recipe is a test baseline, not a match to the Pixel's embedded JPEG processing or earlier creative edits. Color/exposure differences between those sources and this reference are not caused by the mask.

Pixel preservation
Black composites use straight alpha multiplication in the encoded 8-bit sRGB values: round(reference_RGB × mask16 / 65535). Pixels under a fully white mask are identical to the reference; fully black mask pixels are black. Partial alpha naturally darkens an edge on black. Foreground colors are not regenerated or decontaminated, so original background color contamination can remain at edges.

Model and reproducibility
Model: ZhengPeng7/BiRefNet_dynamic-matting
Pinned source and weights revision: 074df545be87034e74a96bf71566ecbbc4c15f0a
Official model: https://huggingface.co/ZhengPeng7/BiRefNet_dynamic-matting/tree/074df545be87034e74a96bf71566ecbbc4c15f0a
Official project: https://github.com/ZhengPeng7/BiRefNet
License: MIT, as listed by the author.
Model weights SHA-256: ae177d331c79dcb849ef5b8aea39cea6effd6ca0df36b5a41431658f990e9ee7
Inference: local CPU, float32, evaluation mode, ImageNet mean/std normalization, final-output sigmoid. Weights were loaded as safetensors, with network-offline model loading and no external photo processing service.

How to judge this test
Inspect both the overview and full-size files. Fine hairs, antennae, narrow gaps, contact points, soft focus and subject-versus-support selection are the hardest cases. A plausible thumbnail can hide missing appendages or a bright rim. Visual assessment is qualitative: no hand-labeled ground-truth masks or objective accuracy score are available. These masks are starting points, not a guarantee of print-ready cutouts.
