# Fixed-size series framing design

Date: 2026-10-20. Status: written design candidate revised after independent review; user decisions and approval remain pending. This is not a step-by-step implementation plan. The user requested Superpowers planning and then independent review. Application changes, Git writes, publication, dependency installation and photographic acceptance are outside this planning task. Review findings and dispositions are retained in [the independent review record](../plans/2026-10-20-series-framing-review.md).

## 1. Intended result and confirmed choices

The user wants a series of photographs whose differently shaped subjects, such as a long grasshopper and a round flower, sit consistently within **identical output dimensions**. Side margins are the main composition control. Reuse the framing feature and existing masks; do not require another segmentation or matting run.

Confirmed: fixed output width/height rather than variable-height exports; a framing control within the current viewer; reuse of the existing framing work. The preceding conversation proposed a side-margin target, minimum vertical clearance, automatic centring, visible height-limited exceptions and reusable series settings. This document makes those proposals concrete for review; it does not treat the example numbers as user-selected production settings.

Success: two saved photo projects can use the same settings and produce the same pixel dimensions. Each subject approaches the same left/right margin target, unless height limits its fit. The preview explains the actual fit. Original captures, native masters, masks, guides, saved effects and accepted revisions remain unchanged.

## 2. Baseline and authority

The application inspected for this design is commit `90829e007f8af677a8ef29694a3f81494b1f07f2` on `framing-and-margins`, with a clean working tree. It contains the published framing candidate from MR #16. Remote state was not refreshed for this planning task; no merge or hosted-review completion is inferred.

The planning repository still has no application source and has pre-existing modified/untracked files. This design is a new file beside the earlier Superpowers designs. Do not implement against that source-free checkout or overwrite earlier plans. Recheck the actual application checkout, instructions, branch/diff, storage contracts and relevant predecessor evidence before execution. A later photo-library/storage migration must be consumed through its actual canonical interfaces, not a parallel resolver invented here.

During independent review, the existing framing handoff recorded a separate owner repairing successful export reuse for MR #16; `tests/test_framing.py` became modified while HEAD remained `90829e0`. That work is outside this review. Before series implementation, reconcile the completed repair, its resulting comparison baseline and affected export tests. Do not take over its checkout while another writer is active or treat the historical clean snapshot as current authority.

Authority order: direct current user instructions; applicable repository instructions; current application `docs/file-contract.md`; the supplied v4 product specification; this proposed additive design. The prior padding-only contract remains authoritative for existing Add margins mode. Resizing and subject-relative layout are new behavior isolated to Match series mode, not a relaxation of the existing exact-copy promise.

Prior Gate 2/3 preapproval and the three-reviewer amendment were recorded for the two original framing increments. Do not silently transfer that program's completion, human approval or review results to this new feature. Preserve the user's one-orchestrator, persistent implementation-owner, sequential-writer and configured-model preferences if execution is later authorized. Add no controller, ledger, scheduler, batch queue or unrelated delivery machinery.

## 3. Approaches and recommendation

1. **Recommended: presentation-only series layout.** Use the selected saved foreground, alpha and appearance settings, compute subject bounds, then render a separate fixed-size delivery. Reuse existing validation, preview UI and safe export publication. Original editing coordinates remain native.
2. Derive four padding values around the complete source image. This reuses more of the existing geometry but cannot provide consistent subject-relative framing across different crops and native resolutions. It does not satisfy the chosen outcome.
3. Resize/crop the working master and all masks/effects. This requires identity/registration migration and changes the editable source for a presentation requirement. Excluded.

The first version handles one photograph at a time. Applying the same preset to another photograph is part of the manual workflow, not a batch-processing subsystem. Automatic optical-weight matching, rotations, arbitrary subject selection, generative expansion and artistic corrections are outside scope.

## 4. Viewer controls

Extend **Framing and margins** with a mode selector: **Add margins** and **Match series**. Add margins retains the existing controls and exact-copy behavior. Switching mode retains each form's unsaved values, clears the displayed stale preview and never saves or exports automatically.

Match series controls:

| Control | Proposed behavior |
| --- | --- |
| Preset name | Human-readable text, 1–80 characters; display as text, never HTML or a filesystem path |
| Output width / height | Positive integer pixels; start at 4000 × 5000 only as editable first-use defaults |
| Side margins | Linked slider and numeric field, 0.0–45.0%, step 0.1%; default 15.0% on **each** side |
| Minimum top/bottom | Numeric field, 0.0–45.0%, step 0.1%; default 5.0% of output height on each side |
| Preview framing | Explicit calculation/render from the selected complete saved revision |
| Show subject bounds | Optional display outline; no mask editing or authoring coordinates on this canvas |
| Save for this photo / Reload saved series settings | Explicit project-local persistence; no silent save while editing or importing |
| Reuse preset controls | Determined by the storage decision in section 8 |
| Export selected accepted result / Export selected revision as draft | Both target the complete saved revision selected in the viewer; accepted export is enabled only when that selection is the current accepted revision. Show the revision and accepted/DRAFT status before the action. Add margins keeps its existing buttons and behavior. |

Show the actual output size, actual four margins, enlargement factor when greater than 1, and fit reason. Examples: “Side margins matched”; “Height limits the fit; actual side margins are 22%”; “Enlarged 1.3×; no additional captured detail.” Explain that bounds describe the existing mask and do not detect anatomy.

All inputs have persistent labels and keyboard operation. The numeric side-margin field provides a non-drag alternative. Status uses the established live-status region. Maintain visible focus, existing production CSP and native authoring behavior. A stale preview cannot be mistaken for current settings or the selected revision.

Every series preview/export request carries the selected master identity, revision ID and expected revision-manifest SHA-256 together with the visible validated settings. Capture these from the same selection shown by the form; never substitute `working_revision` or `accepted_revision` silently. Canonical export validation compares the expected identities after acquiring the project lock and again before publication. Accepted export additionally rechecks that the selected revision is still accepted; explicit draft export stays DRAFT even if its selected revision happens to be accepted. A changed manifest/source/acceptance target produces an actionable stale-input error, not a different export. Changing the selection or settings invalidates the preview; export need not require saving the preset, but always identifies its actual target and visibly marks any stale preview.

## 5. Subject bounds and layout

Use the selected saved `base_alpha16` and include **every pixel with alpha > 0**, including disconnected components, faint partial values and protected details. Compute the smallest half-open rectangle containing them. Do not threshold away faint pixels, select only the largest component, change the mask or silently discard outliers.

An empty mask blocks series preview/export with an actionable message. A mask touching a source edge warns that framing cannot restore already clipped detail. Show the measured outline so the user can notice stray alpha; correction remains an explicit native mask-editing operation outside this feature.

For output dimensions `W,H`, side fraction `m`, vertical fraction `v`, and measured subject dimensions `bw,bh`:

```text
available_width  = W * (1 - 2*m)
available_height = H * (1 - 2*v)
scale = min(available_width / bw, available_height / bh)
```

Use one continuous pixel-edge transform with that uniform scale. For source bounds `(x0,y0,x1,y1)`, the translation is `tx=(W-scale*bw)/2-scale*x0`, `ty=(H-scale*bh)/2-scale*y0`; map every source edge by `(scale*x+tx, scale*y+ty)` and sample at output pixel centres. Do not independently round the subject's width, height or placement. Integer rectangles are only buffer/support envelopes and never define a second scale. Return the continuous transformed subject bounds, uniform scale, translation, integer support envelope and geometric margins. Round values only for display. Reject nonpositive/nonfinite interiors or transforms before allocation.

The percentage controls and reported margins refer to the continuous transformed bounds of the original positive-alpha mask, not to the first nonzero pixel after filtering. Filtered support can extend beyond those geometric bounds; a display outline and help text must preserve this distinction. The geometry must allow subpixel-thin features: a `10000 × 1` subject at scale `0.4` is `4000 × 0.4`, not an independently resized `4000 × 1` opaque strip. For `H=5001` and 5% vertical clearance, each geometric margin can be exactly `250.05` pixels without forcing integer clearances that break the requested fit.

Height wins when necessary, so side margins may exceed their target. Do not stretch, crop photographed subject content or rotate it to force a match. Enlargement is permitted only as explicitly labelled resampling of existing detail. It does not run a super-resolution model. Equal width does not guarantee equal perceived visual weight; individual artistic size/position overrides are deferred from this first version.

## 6. Rendering and photographic contract

Use validated saved RGB16 foreground, grayscale16 alpha and the canonical selected appearance layers. Resolve exposure, cleanup and Shadow fade through `saved_layers`/`selected_foreground`, and shading through `saved_shading`; reject stale enabled effects rather than silently exporting the base fallback. Every effect and alpha is applied once.

The proposed series resampler operates on floating-point premultiplied foreground contribution and alpha with the **same geometry and filter**. Reuse the current encoded-sRGB shading/compositing convention; do not quietly change native rendering to a different colour space. Factor a small shared contribution helper only where it removes actual duplication between the existing renderer and the new consumer.

Use the already pinned Pillow's scalar floating-point `F` images per channel with an explicit Lanczos filter; do not pass RGB16 through Pillow's 8-bit RGB/RGBA modes or the browser preview. Derive fractional source boxes from the same continuous transform for all channels. Preserve the full scale-dependent filter neighborhood with transparent zero contribution/alpha beyond the captured image; the tight subject box must not become a clamped/repeated image boundary. Use bounded explicit support/zero padding where the library requires finite input boxes. Do not substitute Pillow's affine transform API with a different filter while labelling the result Lanczos. The implementation plan must pin the mapping/support calculation and scalar float64-oracle tolerance before code; a new resampling engine is not presumed necessary.

Define the overshoot policy in this order: reject nonfinite filtered values; bound filtered alpha to `A=clip(alpha,0,1)`; bound each filtered premultiplied RGB16-range channel to `P=clip(contribution,0,65535*A)`. Use this same bounded `(P,A)` pair for the composed and transparent variants. Compose against output backdrop `B` as `P+B*(1-A)` and quantize once to RGB16. This maintains `0 <= P <= 65535*A` rather than independently clipping colour and alpha to incompatible ranges. Test contrasting partial-alpha edges with real negative-filter-lobe overshoot as well as hidden saturated colours under zero source alpha. Output samples are resampled, not bit-identical native pixels; native protected pixels and masks remain byte-identical on disk.

**Proposed background decision for written review:** generate the selected revision's saved background recipe at the final output dimensions using the existing background generator; use black for a legacy revision without background settings. Validate the saved settings and algorithm identity against their manifest first; an unsupported saved background algorithm blocks series rendering rather than being silently replaced. This gives the full fixed canvas a continuous backdrop and avoids stretching an already flattened subject or repeating image-edge strips. It changes the placement of a textured/varied backdrop compared with Add margins; disclose that distinction in the UI/docs and manifest. It never rewrites the saved native backdrop or changes its controls. Matching background colour across photos remains the user's existing Background control, not a new series-preset override.

For transparent viewing output, unpremultiply `P/A` only where bounded alpha is positive, then quantize straight RGB and alpha to RGBA8. After quantization, set RGB to zero wherever the **quantized** alpha is zero, including positive floating alpha that rounded down. No second alpha multiplication and no background baked into transparent RGB. At extreme reductions, fine details may become subpixel and visually disappear despite correct resampling; require visual inspection and do not promise their native appearance at every output size.

Preview uses the same layout/subject/render semantics at a display long edge of at most 1600. It must not allocate the full output canvas just to preview it. Generate the background according to output geometry, then sample it for display; preserve the full requested grid's mean/extrema normalization, computed in bounded rows, rather than deriving those statistics on the preview grid. This avoids a different backdrop pattern, but the statistics pass still has output-size-dependent computation: measure preview latency, not only memory. A direct reduced render is an approximation of final sampling, not a pixel-exact substitute for exported TIFF inspection.

## 7. Reuse and file responsibility

All application paths below are relative to the verified application checkout, not this planning repository.

| Owner | Responsibility |
| --- | --- |
| Existing `src/blackmask/framing.py` | Retain validated exact padding, schema-1 margin presets and their compatibility; reuse only genuinely common validation/geometry utilities |
| Proposed `src/blackmask/series_framing.py` | Strict series settings, mask bounds, layout, resampling and source-bound series preset handling |
| Existing `src/blackmask/export.py` | Reuse validated saved layers, selected-revision rules, contribution arithmetic, locks, input snapshots, round-trip validation and exclusive publication; add explicit series export mode |
| Existing `src/blackmask/background.py` | Reuse background validation and canonical generator; any sampled-output helper must retain one field definition and have a full-canvas reference oracle |
| Existing `src/blackmask/viewer.py` | Authenticated series preview/save/export actions; source/revision/setting identity checks and bounded concurrent work |
| Existing `src/blackmask/ui/review.html` | Mode-specific controls, independent form state, safe preset loading, explicit actions and stale-preview rejection |
| Existing `src/blackmask/cli.py` | Explicit series preset option, mutually exclusive with manual margins, with the existing draft/revision selection rules |
| Proposed `tests/test_series_framing.py` and existing CLI/viewer/browser tests | Observable new behavior, precision, compatibility, persistence, failure and browser journeys |
| Existing maintained workflow/file-contract/troubleshooting/validation docs | Supported interface and evidence; no runtime dependence on this local design |

Do not create a generic rendering framework, plugin registry, second project store or duplicate native export pipeline. The existing padding functions are not suitable for resizing unchanged; reuse their surrounding contracts and helpers, not their exact-copy claim.

## 8. Preset persistence: user selection pending

A focused question has been sent to the user. Do not resolve it by elapsed time or assume the earlier illustrative dropdown chooses a storage architecture.

**Recommended candidate: portable local preset file.** A settings-only JSON file contains schema version 1, kind `series-framing-preset`, name, output width/height and side/vertical percentages represented as integer tenths of a percent. No image, mask, path, source identity, credential or photograph metadata is included. Load through an explicit browser file picker and validate bounded bytes on both client and server; no server-side arbitrary-path endpoint. Saving a portable file uses an explicit download; cancellation does not claim success or modify the photo project. Use Load preset file / Download preset file rather than pretending to offer an app-wide dropdown.

The project keeps its own optional `series-framing.json`, separate from existing `framing.json`, containing schema version, source identity/dimensions and a full snapshot of the selected series settings. Saving is explicit, uses the existing project lock and raw-byte compare-and-swap pattern, and revalidates source identity before publication. A later edit to a portable preset cannot silently alter an already saved photo configuration or export. Absence selects defaults without writing a file; invalid files remain preserved and only disable the affected series save/reload flow.

**Alternative: app-wide named preset dropdown.** This requires a new explicitly scoped local catalog location, concurrent catalog locking, stable preset identities, missing/changed-preset handling and backup/recovery. The current viewer is intentionally restricted to one project. If the user selects this alternative, amend this section and review that concrete storage/security contract before the implementation plan; do not implement both options or choose an implicit global directory.

## 9. Export identity, compatibility and failure behavior

Create a distinct compact presentation delivery under the current project's exports directory. Identify it as `series-framed-presentation`; bind its immutable identity to validated source and revision-manifest bytes, selected effects/background, settings, measured bounds, actual placement/scale, resampling/background algorithm versions, colour encoding and requested output variants. Include those settings and identities in the manifest, excluding personal paths and private capture metadata.

Retain RGB16 TIFF, RGB8 viewing PNG, optional straight RGBA8 viewing PNG, manifest and readable delivery notes. Notes explicitly state that this is a resized presentation and the native editable project remains authoritative. Accepted-input labelling must not imply separate human acceptance of the series composition. A selected unaccepted revision remains DRAFT.

Existing native exports, Add margins exports, schema-1 `framing.json`, saved masks, recipe/guidance digests and accepted/working pointers retain their contracts. No automatic migration or rewrite on read. The CLI must reject combining series settings with manual pixel margins. Viewer actions use the visible validated series settings, including unsaved edits, without silently saving them.

Retain the existing 32768-pixel axis and 100000000-pixel output limits and 10 GiB disk reserve. Validate geometry before output allocation/staging. Admission must include selected input buffers, sequential floating-point resampling buffers, output/readback and variant storage; a disk check is not a RAM guarantee. Preview allocation depends on native inputs and reduced display buffers, not the full requested output. Measure a representative full export before declaring resource readiness.

Before publication, recheck the exact source/revision/settings identities consumed. Serialize conflicting writes; reject stale raw preset digests and stale selected revisions. After uncertain post-replace durability, preserve form edits, report actual visible state and require explicit reload before another save. Failed exports preserve accepted data and prior deliveries; validate a complete matching delivery before reusing it. Do not overwrite corrupt collisions, follow symlinked preset/output paths, delete recoverable staging automatically or silently lower limits/precision to succeed.

## 10. Acceptance and verification coverage

| Requirement / risk | Required evidence |
| --- | --- |
| S1 Fixed size and width-driven fit | Literal rectangle, horizontal insect and circular flower fixtures with different source sizes produce exactly W × H; independent continuous scale/translation and geometric-margin oracles |
| S2 Height-limited exception | Tall subject fits vertical clearance and reports wider side margins; H=5001 at 5% has geometric clearances 250.05; 10000 × 1 at scale 0.4 retains a 0.4-pixel geometric height; integer support envelopes never supply a second scale |
| S3 All real masked detail participates | Alpha 0, 1, partial and 65535; disconnected tips/source-edge content; empty/full masks; zero-padded impulse/partial-edge scalar references that fail tight-crop renormalization; singleton axes and non-integer scales |
| S4 High-precision resampling | Non-257 RGB16; identity geometry; independent float64 scalar oracle with declared tolerance; real Lanczos overshoot at contrasting partial edges; 0 <= P <= 65535*A; black/nonblack composites; shading/alpha once; RGB zero where quantized RGBA8 alpha is zero |
| S5 Background and transparency | Constant and varied saved backgrounds; legacy black; full-output reference versus reduced preview; straight RGBA8 readback and zero-alpha RGB |
| S6 Reproducible delivery | Actual TIFF/PNG readback, manifest/algorithm/settings identities, saved-only replay in a new process with model/capture unavailable, no private metadata in delivered files |
| S7 Persistence and recovery | Both byte-level stale CAS and two-process locking; invalid/oversized/unknown-field presets, failed writes before/after replace, explicit reload and preserved unsaved edits; storage-specific tests follow the selected section 8 design |
| S8 Resource and publication safety | Rejection before large allocation; peak resource measurement; 10 GiB reserve; interruption, corrupt/missing/extra/symlinked output and source/revision changes preserve prior usable work |
| S9 Actual browser flow | Production CSP; keyboard numeric/slider alternatives; mode switching; delayed old response; two tabs; preserve unrelated dirty forms; selected != working != accepted with both series buttons targeting the named selection; changed expected manifest/acceptance rejection; visible unsaved settings; reopen/reload |
| S10 Compatibility and human result | Existing framing/native regression suite plus a local flower and long-subject visual comparison when authorized; no claim that numerical tests establish photographic acceptance or full accessibility |

Use small synthetic fixtures first. Run focused failing/passing application tests during each coherent change and the full relevant deterministic suite/static checks once on the settled candidate. The existing README's pytest, Ruff and mypy commands are verified command definitions, not new test results. Reuse prior evidence only when its actual tested inputs still match; record changed scopes and renew only affected reviews.

Recommended delivery is one detailed Superpowers implementation plan in one fresh thread with one persistent implementation owner and sequential testable checkpoints: (1) strict settings parser, continuous geometry/resampling and usable safe CLI export; (2) the selected reusable-preset persistence and recovery contract; (3) integrated viewer controls, browser verification and maintained docs. Establish rendering oracles before export integration and include the settings parser with the CLI consumer, not a later persistence task. Each checkpoint includes its own relevant tests and direct-consumer contracts. Carry progress/evidence in the plan and existing logs; add no separate ledger/controller/scheduler. One final independent code review remains distinct from this design review; renew only affected review scopes after repairs.

A separate coordinated incremental-plan/QA/handoff program is not needed for this bounded, coupled feature. Reconsider that recommendation if the user selects an app-wide catalog requiring a separately useful shared-storage subsystem, requests separate releases/approvals, or materially broadens scope. A fresh thread and internal checkpoints are compatible; this is not a recommendation for one unverified bulk change. This outline is not the step-by-step implementation plan, which follows written-design approval under the selected Superpowers workflow.

## 11. Current sources and evidence limits

Official sources checked live on 2026-10-20:

- [Pillow 13.0.0 modes and precision](https://pillow.readthedocs.io/en/stable/handbook/concepts.html): scalar floating-point F mode is available; ordinary RGB/RGBA modes are 8-bit. This supports per-channel processing, not an automatic proof of RGB16 correctness.
- [Pillow resize API](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.resize): explicit filter, output size and source-box parameters. The pinned environment must still pass the actual float-channel and alpha oracles.
- [Pillow 13.0.0 resampler source](https://github.com/python-pillow/Pillow/blob/13.0.0/src/libImaging/Resample.c): scale-dependent Lanczos support, boundary weight handling and unclamped floating output informed the corrected geometry/overshoot contracts. Source inspection is not runtime proof.
- [W3C alpha compositing](https://www.w3.org/TR/compositing-1/#simplealphacompositing): premultiplied contribution and source-over arithmetic. It does not establish this application's colour-space or photographic-quality decisions.
- [WCAG 2.2 dragging alternatives](https://www.w3.org/WAI/WCAG22/Understanding/dragging-movements.html): supports a non-drag numeric control alongside a slider. It does not certify accessibility of the finished viewer.

The inspected stack is Python >=3.12,<3.13, NumPy 2.3.5, Pillow 13.0.0 and tifffile 2026.10.15, with existing HTML/JavaScript and pytest/Node checks. No dependency or model change is proposed. This task has performed source/documentation inspection only, not a new resampling experiment, application test, model run, browser validation or photo export.

## 12. Written review and resumption

Checklist for this planning stage:

- [x] Reconcile the user's fixed-dimensions choice and earlier control proposal.
- [x] Inspect the actual framing/rendering/viewer/storage owners and relevant tests.
- [x] Compare alternatives and verify applicable official documentation.
- [x] Write this concrete design candidate; preserve all existing work.
- [x] Self-review requirements, compatibility, source ownership and S1–S10 QA coverage; no placeholder markers or unbalanced code fences. Preset storage and the written design remain explicitly unapproved, so this candidate is not execution-ready.
- [x] Obtain two distinct fresh-context read-only reviews; verify and correct three material design findings. Preserve the original candidate identity and report scope in the linked review record.
- [x] Both original reviewers closed their affected findings against substantive candidate `9e91cf9486ba317271c402eab7360471a46a652f62a0ce5d5e560ee3e53fdec8`; no directly introduced material issue was found. This checklist update records static design-review closure only.
- [ ] Resolve the preset-storage question in section 8.
- [ ] User reviews the written design, including subject bounds, resized-background behavior and saved settings compatibility.
- [ ] Apply the Superpowers writing-plans workflow to produce the detailed implementation plan and coverage reconciliation.
- [ ] User reviews that plan and authorizes execution; Git/publication and other separate actions remain separately authorized.

Resume from the earliest unchecked item using the same candidate, not a fresh speculative design. No skill instruction to commit overrides the repository's requirement for explicit Git authority. No existing application or earlier planning document was changed by preparing this candidate.
