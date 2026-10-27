# Local sharpening design

Status: updated for independent review before the user-requested preapproved implementation. This document specifies proposed application behaviour; it is not evidence that the control exists.

## Goal and scope

Improve apparent sharpness of existing detail in selected photographic regions while preserving protected areas, colour interpretation, transparency and recoverability. The same control covers hair, feathers, petals, fabrics, eyes and translucent detail. The first private pilot is one example, not a subject-specific algorithm or a claim of general photographic acceptance.

Use a single optional **Local sharpening** effect in the existing offline, native-coordinate appearance workflow. Amount, detail scale and noise sensitivity must accommodate both compressed JPEG and larger RGB16 masters. Do not add subject detection, AI detail synthesis, deconvolution, denoising, resizing, an effect stack editor or a new processing backend.

## Decisions and alternatives

- Recommended: selected luminance unsharp masking with explicit noise and overshoot guards. It adds actual local edge enhancement using installed NumPy/SciPy and fits existing support/protection and revision contracts.
- Tonal exposure/fade alone is insufficient for actual sharpening; that route has already yielded only modest visibility improvement.
- Deconvolution requires stronger blur assumptions; generative enhancement conflicts with source-detail preservation. Neither belongs in this feature.
- Use one adjustment with any number of authored regions and one settings tuple, matching Local exposure. Different concurrent radii per region are outside this scope.

## Settings and manual interaction

Add optional recipe section `local_sharpening` with exactly these strict fields. Numbers must be finite int/float excluding booleans.

| Field | Range | New-project default | UI |
| --- | --- | --- | --- |
| enabled | boolean | false | explicit Apply/Reset |
| amount | 0–1 | 0 | Amount 0–100%, whole percentages |
| radius_px | 0.5–8 | 1 | Detail size, native pixels, 0.1 steps |
| noise_threshold | 0–0.02 | 0.001 | Noise guard 0–2%, 0.01 percentage-point steps |

Detail size is Gaussian sigma, distinct from selection brush radius and feather. These bounds are conservative engineering choices for review, not calibrated quality guarantees. Verify the full supported range on synthetic fine and broader structures; do not retain the earlier dragonfly-specific 2-pixel ceiling. Defaults stay OFF; enabling an area with zero Amount remains an exact identity.

Reuse typed native brushes/rectangles, inward feather, separate hard Protect regions, keyboard numeric alternatives, selection listing/removal, Apply/replace area, Apply amount to saved area, Compare sharpening OFF and Reset. Preserve unrelated pending drafts. The selected subject is not detected automatically. Reset keeps recoverable operands; comparisons never write revisions or change acceptance. An OFF comparison retains current cleanup/exposure/fade/background/framing and recomputes downstream RGB from the unsharpened input.

## One deterministic kernel

New module `src/blackmask/sharpening.py` owns validation, arithmetic and saved operand reading. Reuse the existing sRGB conversion and area-rasterization helpers. Operands are registered RGB16 foreground, unchanged alpha16, support16 and categorical protection including saved guide/RGB locks.

1. Read the cleanup-selected, unsharpened native RGB input. Decode sRGB to float64 linear RGB; compute Y = 0.2126R + 0.7152G + 0.0722B.
2. Compute an alpha-weighted Gaussian mean B = G(Y*A)/G(A), where A = alpha16/65535. Fix `mode="reflect"`, float64 output and integer kernel radius `ceil(4*radius_px)`; do not filter the flattened black/background result. A zero denominator takes the exact input path. Alpha weights the neighbourhood, not the requested write strength.
3. Detail D = Y-B. Apply soft threshold `sign(D)*max(abs(D)-noise_threshold,0)`; multiply by Amount and support16/65535 only for nonzero-alpha, unprotected selected pixels.
4. Bound the candidate luminance to the min/max of valid nonzero-alpha luminance in its 3×3 native neighbourhood. This limits new extrema; it does not promise every visible halo disappears.
5. For Y>0, rescale the linear RGB triplet by targetY/Y. Limit gain to keep every channel in [0,1] without independent per-channel clipping; Y=0 takes identity. Encode only changed samples and quantize once, float64 ties-to-even RGB16.
6. OFF, zero Amount, zero alpha/support, explicit/guide protection and a zero final adjustment copy original RGB samples exactly. Alpha never changes.

This cannot restore missing focus, remove captured background contamination inside a translucent foreground, or establish photographic fidelity by a score. The noise guard is an adjustable suppression threshold, not a denoiser or calibrated noise estimate.

Use bounded row strips with full-width native context and a halo of max(1,ceil(4*radius_px)). Drop halo rows from writes; reflect only at actual image boundaries. Require bit-exact strip/full-frame reference results on independent small fixtures and measured bounded peak memory at larger dimensions. Keep one kernel; no parallel tile worker or separate preview arithmetic.

## Rendering, requests and lifecycle

Rendering order is saved base -> optional cleanup -> **Local sharpening** -> local exposure -> Shadow fade -> inward shading OR spatial background blend -> alpha/background composition. OFF/base comparisons and every native/presentation/gallery/review consumer use that same operation. Audit the existing explicit matte/repair preview composition as well as `selected_foreground`; changing only the latter is incomplete.

Use the existing schema-2 `kind:"effects"` operation. Add exclusive `local_sharpening`, with exactly one replacement area source: `sharpening_area` (regions/protection) OR registered `support_file` plus `sharpening_protection_file`. Add `sharpening_amount_only:true` for saved-area changes. Common master/base/draft/scope/candidate identities retain their meanings. Scope covers old and replacement support; never silently union selections or drop protections.

Persist support16/protection16/current alpha16/settings and optional authored area under `effects/sharpening/`, binding hashes, native dimensions, developed ID, full alpha dependency, strict actual settings, algorithm `linear-srgb-local-sharpening-v1`, scope and candidate-comparison status. Validate dependencies and authored/scalar equivalence even OFF, including rejection of unbound area files before warm validation/cache hits.

Each render starts from current cleanup-selected RGB, never previously sharpened RGB. Cleanup changes recompute the kernel from current RGB; request/reuse identities include that selected input and its cleanup dependencies. Alpha changes make enabled sharpening stale until explicit whole-adjustment rebuild or Reset. Extend prepare/matte/repair inheritance, RGB lock snapshots, effective recipes, stale labels, acceptance/export gates, recovery/context validation and processing-cache inventories. Preserve existing lock semantics without sharpening an already captured selected-RGB lock twice.

Use canonical writer locking, input rechecks, staged complete revision publication and state-last pointers. Update finite effects/export execution identities when semantics change. Preserve old cache entries; a conservative effects cache miss does not authorize model inference or deletion.

## Compatibility and complete delivery

Existing schema-2 projects without this optional section read as OFF without byte rewriting. Schema-1 rejection/migration policy stays unchanged. New sharpening records require the updated application; there is no forward-compatibility promise for older binaries. Do not assert that every old direct reader rejects an unknown effect: older validation has bypass paths. Preserve pre-feature projects/exports for older applications; never strip records or silently migrate accepted work.

New-reader validators reject unknown sharpening record versions and mismatched dependencies. Missing/OFF sharpening must keep existing rendering and delivery behaviour exact. Existing export variants remain independent; do not make manual editable export mandatory.

A final assisted export explicitly includes complete editable layers. Add unsharpened cleanup-selected RGB16 and sharpening support/protection/alpha/settings/optional area. Selected foreground already includes sharpening/exposure/fade once. Unexposed RGB now includes selected sharpening when present; unfaded RGB includes sharpening plus exposure. Explain replay order and ensure selection shortcuts never apply sharpening twice. Bind the new members to both native deliveries and native companions of framed/match-series exports.

Keep plans/private handoff/photos out of installable archives. Existing sources, accepted projects, previous drafts and diagnostics remain retained.

## Verification and acceptance

Synthetic cases must include fine dark/bright lines, wider texture, smooth gradients, controlled noise/JPEG-like blocks, saturated/near-black samples, empty and partial alpha, image/crop/strip edges and protected partial pixels. Test supported radius extrema and middle values, support replacement/removal, exposure/fade/background OFF and ON, saved locks, restore, stale alpha, tampered/off operands, interrupted publication and unchanged request reuse.

Use independent expected values/reference convolution on small fixtures, not the implementation as its own oracle. A blurred line must become steeper within permitted local extrema; a perfectly sharp step may remain unchanged under the overshoot guard. Threshold suppression must be proven on a low-amplitude fixture without claiming real noise removal.

Run relevant application suites, lint, formatting and source types once for settled inputs; inspect archives and saved-only native/companion reconstruction. Keep the already-recorded unrelated intermittent viewer-lock baseline qualification separate; do not silently fix it or weaken checks.

Only after engineering evidence and independent result review: try a mild setting on the existing selected private photo using project controls, protect non-target regions, inspect native source/alpha/black/gray/white and OFF comparisons. At most one stronger candidate if the first clearly improves detail. Preserve the prior draft; stop on artifacts, ambiguity or no improvement. Additional private photographs require selection/authority; synthetic breadth does not imply photographic acceptance across subjects. Final acceptance remains human.

## Authority

The current user requested updating this plan, independent plan review, and a new implementation chat with preapproval. Routine in-scope local implementation, relevant tests and verified fixes may proceed after actual plan review closure, without another routine approval question. Material design/scope/compatibility changes still require a human decision.

No publication, commits, pushes, PR/provider requests, merges, installs/downloads, private uploads, permission repair or cleanup/deletion are included in this new feature grant. Prior I13–I19 provider deadlines/counters and photographic acceptances are separate and unchanged.

## Sources checked

- https://scikit-image.org/docs/0.26.x/api/skimage.filters.html#skimage.filters.unsharp_mask — general method and luminance-channel rationale; this is reference documentation, not a dependency addition.
- https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.gaussian_filter.html — explicit kernel bounds, boundary handling and output precision. The retained installed SciPy 1.17.1 signature was inspected locally; current public documentation is a newer version.
- Repository owners: README.md, docs/file-contract.md, docs/workflow.md, docs/assistant-workflow.md; existing exposure/shadow-fade/effects/recipe/project/export implementations.
