EDGE-SHADOW EVALUATION — 11 October 2026

Recommendation
Use this selectively. The dahlia benefits modestly from the subtle version, especially its lower/side perimeter. The grasshopper already has a soft edge; the extra shading changes less and is not automatically better. Start with the 12% version or lower. The 24% version is an intensity comparison, not an approved final grade.

What this is
A reversible two-picture study at the original developed-image dimensions, 3072 x 4080. The original photograph and existing subject mask remain separate and unchanged. No generative redraw, new detail, new segmentation or batch replacement was performed. These previews use the previously supplied 8-bit sRGB developed PNGs, not a new RAW development. The separate 16-bit developed masters and DNG originals remain untouched.

Files in each subject folder
- BASE_SUBJECT_MASK_16BIT.png: unchanged copy of the existing subject alpha.
- SHADOW_WEIGHT_16BIT.png: editable relative effect mask. White allows full chosen layer opacity; gray allows less; black protects the pixel. This is NOT a replacement cutout mask.
- SUBTLE_BLACK_LAYER_RGBA.png: black overlay with up to 12% alpha, already baked into its transparency.
- MODERATE_BLACK_LAYER_RGBA.png: black overlay with up to 24% alpha.
- SUBTLE_FULLSIZE_PREVIEW.png / MODERATE_FULLSIZE_PREVIEW.png: flattened 3072 x 4080 reference previews.

The original RGB files are not repeated to keep this package small. Use these exactly aligned originals from the earlier photo packages:
- Grasshopper: 01_1000036098_developed.png (Photo 01)
- Pink dahlia: 05_1000035853_developed.png (Photo 05)
The corresponding 16-bit TIFF masters have the same geometry and can be used for a higher-precision editing stack; the included previews are based on the 8-bit PNG reference. A different RAW conversion, crop, lens correction or rotation must be aligned first.

Suggested non-destructive layer stack (top to bottom)
1. Foreground group, with BASE_SUBJECT_MASK_16BIT as the group's mask:
   a. Solid black layer, Normal blend, 12% opacity, with SHADOW_WEIGHT_16BIT as its layer mask.
   b. Original developed RGB image, unchanged and unmasked inside the group.
2. Solid black background.

The group mask applies the subject transparency once to the complete foreground stack. The separate shadow mask controls only edge shading. This keeps the source and alpha editable. Use 0% opacity to return to the baseline, 12% for the subtle test, and 24% for the stronger test. Paint black into the shadow mask to protect any extra hair, antenna, petal tip or true highlight. Avoid applying the base mask twice.

Convenience PNG alternative
Within the foreground group, use ONE supplied RGBA black overlay at 100% layer opacity above the RGB source instead of the solid-black layer and shadow mask. Its effect strength is already in the PNG alpha: do not apply another 12%/24% opacity unless intentionally reducing the effect. For an already flattened black-background result, the same PNG can be placed above it directly. For transparent output, retain the masked-group arrangement so the shadow does not change subject coverage.

Parameters and behavior
- Grasshopper: smooth inward falloff to zero over 48 original pixels.
- Dahlia: smooth inward falloff to zero over 88 original pixels.
- 14-pixel core radius plus a soft thickness gate protects isolated narrow details; this is a heuristic, not semantic understanding.
- More weight on side/lower-facing edges; less on top-facing edges and bright highlights.
- Very low-alpha pixels receive less effect, and zero-alpha background is unchanged.
- All pixels deeper than the specified inward band are unchanged.
- These are maximum layer opacities. Most affected pixels receive considerably less.

Color-management caveat
The previews match the earlier test's arithmetic in encoded sRGB: output = RGB x subject alpha x (1 - opacity x shadow weight). This is an aesthetic, reproducible edit, not physically linear-light relighting. A linear-light document or a different compositing-gamma preference will render the same numeric opacity differently; judge the result in the final document rather than copying the percentages blindly. Treat grayscale masks as scalar coverage data; do not color-grade or gamma-correct them.

Visual assessment
- Subtle dahlia: mild softening of the perimeter without a new hard rim in the inspected native crop. Internal petal shading and the central bee are unchanged.
- Subtle grasshopper: very small benefit; preserve the natural bright dorsal rim. An isolated antenna crop is pixel-identical even in the 24% test.
- Moderate: stronger roll-off, particularly on the flower. It is easier to make the outer petals look unnaturally shaded if increased further; a uniform ring should be avoided.
- These edits do not fix a wrong mask, photographed background contamination, missed hairs, or optical softness. Fix those separately first.
- The repaired spider/web was inspected as a cautionary case, not edited here. A generic edge-darkening ring is especially risky for web strands and fine hairs; any later test should target broad body edges and explicitly protect the web.

Reviewing the study
Edge-shadow-comparison.jpg shows whole-frame postcard-size results. The two native-crop PNGs use unresampled 512 x 512 source crops per panel. View those at 100% display scale for a native-pixel comparison. The full-size PNG previews let you inspect every edge. This study is a starting point for choosing an effect, not an instruction to apply it across the photo set.

Validation
Original source/mask hashes were unchanged. Empty background and the interior beyond each effect band are unchanged. The isolated grasshopper antenna and the flower-centre/bee crop have maximum channel difference 0 in the moderate test. See evaluation_checks.json for coordinates, source hashes and parameters. All assets are aligned full-size; no image resizing was used to generate the effect itself.
