HISTORICAL RESULT README
The workflow folder mentioned below belongs to the original spider-result archive. In this curated reference, corresponding code and metadata are under guided_mask_test/ and not every historical intermediate is included. See the top-level README before attempting execution.

SPIDER AND WEB: BACKGROUND-RESIDUE REPAIR

1536 x 2040 native pixels. All principal PNGs are aligned. The original DNG upload remains unchanged and is not duplicated in this compact package.

Start here
- BLACK_COMPOSITE.png: repaired spider and web on black.
- TRANSPARENT.png: ready-to-use repaired foreground with 8-bit alpha.
- MASK_16BIT.png: editable full-precision soft transparency mask.
- FOREGROUND_COLOR_REPAIRED.png: the RGB layer used for the repaired composite. Use this with MASK_16BIT.png.
- SOURCE_ALIGNED.png: untouched RGB from the previous documented RAW development. This remains an aligned reference; it is NOT the color-corrected foreground layer.
- TRIMAP.png: repaired background/unknown/solid guidance.
- LOCAL_REPAIR_SUPPORT.png: the area allowed to receive the localized correction.
- CHECKS.json: pixel-exact preservation and composite checks, gap-opacity measurements, and file hashes.

What changed
The earlier mask retained photographed background in several empty gaps around the spider's legs. Four measured gap regions had median opacity of roughly 10%, 21%, 24%, and 31%; their revised median opacity is zero. Five small, visually verified background cores were added to the guide, followed by one new 1024 x 1024 native-pixel ViTMatte pass. Its result was blended only around the spider and prey. Original fully opaque anatomy remained locked. The standalone web outside this support is pixel-identical to the previous result.

A small localized foreground-color cleanup also reduces photographed-background spill in partial-coverage pixels. It estimates nearby background color and applies a bounded inverse-mixture adjustment. This is an approximate color decontamination, not a physical ground-truth reconstruction. Opaque subject RGB is unchanged. No global desaturation or warming was used. No new visual detail was generated.

How to edit
For the repaired result, apply MASK_16BIT.png to FOREGROUND_COLOR_REPAIRED.png. Applying the same mask to SOURCE_ALIGNED.png gives a mask-only variant with the original developed colors. SOURCE_ALIGNED.png and FOREGROUND_COLOR_REPAIRED.png are deliberately distinct and labeled.

Limits
Optical softness and grain in the original capture remain, particularly on defocused rear legs. Some mixed color is inseparable from very soft detail in a single photograph. The mask and color estimate are guided approximations. The RAW development uses the previous approximate metadata white balance, documented in workflow/RAW_DEVELOPMENT.json. This repair does not attempt to reproduce the phone JPEG's tone mapping or the sharper appearance reference.

Workflow files
The workflow folder includes the previous matte, SAM subject guide, corrected gap cores, new local matte crop, crop bounds, model versions, and method code. run_guided.py expects the pinned model files described by MODEL_MANIFEST.json in a models directory. repair_method.py records the exact processing and QA logic used in this repair and references the working-project folder layout; it is supplied for inspection, not as a standalone application.

Original capture
The original uploaded RAW file is not repeated in this compact archive. Its upload remains untouched. It has a .jpg filename but contains DNG data. SOURCE_ALIGNED.png preserves the untouched developed RGB used for this repair; FOREGROUND_COLOR_REPAIRED.png is the separately labeled corrected layer.
