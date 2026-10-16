PHOTO WORKFLOW REFERENCE — RESEARCH PROTOTYPE
Prepared 11 October 2026

RUN ONLY AFTER REVIEW.
This is a curated research reference for planning a local implementation. It is not a turnkey application, installer, portable project, production pipeline, or promise of identical results on another computer. No software or model was installed by this packaging step. Do not run the scripts unchanged.

Start with TECHNICAL_REFERENCE.txt, INPUT_OUTPUT_CONTRACT.txt and PORTING_CHECKLIST.txt. The separate handoff document and planning prompt explain the desired future workflow. Establish the local plan before installing or implementing anything.

Contents
- mask_test/: initial batch baseline scripts, exact historical manifest and validation, the three historical contract tests, RAW recipe and environment snapshot.
- guided_mask_test/: the selection/matting runner, final hand-guided selection and trimap logic, local correction code, pinned model metadata/configuration and example coordinates.
- edge_shadow_evaluation/: independent adjustable edge-shading study. Its README describes the old study's 12%/24% comparison; the current direction is adjustable, with 24% only tentative.
- examples/: limited full-size spider-repair layers, a dragonfly source JPEG and final mask, and independent dahlia shading/base masks. These are reference fixtures, not the full project layout expected by the scripts.
- previews/: small visual records of the guided result, repair and shading comparisons. Their display sizes are not source resolution.
- requirements/: observed inference and postprocessing versions, not a universal install lock.
- SOURCE_PROVENANCE.json: source-relative provenance and hashes. Scripts only had the original absolute workspace prefix replaced with /path/to/photo-workflow-reference, without algorithm changes.
- MODELS_AND_LICENSES.txt / MODEL_REFERENCE.json: exact checkpoints and links. No model weights or third-party model implementation code are bundled.
- PACKAGE_AUDIT.json / SHA256SUMS.txt: packaging checks and file integrity.

Important limits
The best results used reviewed SAM candidates, manually specified positive/negative points, manually edited trimaps, source-visible web corridors, inspection at native scale and repeated matting passes. None of those decisions is yet a general automatic workflow. Coordinates and dimensions in the supplied guide/repair scripts describe these photographs only.

The spider's final repaired color layer is deliberately distinct from the untouched developed source. It uses approximate local color decontamination on partial-coverage pixels. Mask-only work preserves developed source RGB; optional decontamination and optional shading do change RGB and must stay reversible and separately labeled.

No generative synthesis, new hairs, invented web strands, replacement geometry, sharpening or image-generation model was used. A source-guided mask cannot recover detail absent from a photograph.

Excluded intentionally
Model weights, virtual environments, caches, original DNGs, the complete photo collection, redundant exports, transfer utilities, upload records and unrelated files. Downloading or installing missing components is a future reviewed implementation step.

The archive can be extracted and read without executing anything. Some scripts write to fixed output names; they could overwrite derived files if run in the wrong layout. Protect originals, make a separate test workspace, adapt paths explicitly and add output-collision safeguards first.
