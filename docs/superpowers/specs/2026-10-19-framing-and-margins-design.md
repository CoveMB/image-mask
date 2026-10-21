# Framing and margins design

Status: proposed design for user review; planning and one independent plan review are authorized. Product implementation, Git publication and photographic acceptance are not authorized by this document. Date: 2026-10-19, America/Toronto.

## Intent and success

The user photographs insects and flowers close to the image boundary and wants more room around complete legs/petals, easier centring and freedom to crop later. Add background space without stretching, resampling, clipping or inventing photographed detail. Keep the complete offline/manual workflow.

Success is a framed export with the original rendered image copied exactly into a larger canvas, configurable margins, a useful preview and reproducible saved layout. All source pixels, native masks, effect operands, editing coordinates and accepted revisions remain unchanged. A cut-off leg stays cut off; this feature cannot reconstruct it.

The outstanding optional preference asks whether to include automatic subject centring. This candidate recommends **manual placement plus centre-image**, with no subject detector or alpha-bound heuristic. That is a proposal, not an inferred user answer. It can be reviewed now; a different answer requires revising the affected design before implementation.

## Evidence and integration boundary

The planning checkout has no application source. The inspected implementation is the background-appearance checkout at `037e8fb4f62774fc85e4fe63e5029bcca832d877`. Its locally available `origin/background-appearance` differs only in troubleshooting documentation; no fetch or remote-state verification was performed. Exact paths, dirty state and file hashes are in `local/plans/framing-and-margins/source-baseline.json` at the planning repository root.

Current owners are `export.py` for saved-layer rendering/publication, `background.py` for saved native RGB16 backdrops, `project.py` for validation/locking/atomic writes, and `viewer.py`/`ui/review.html` for authenticated local controls. Existing review crops and authoring are explicitly in native image coordinates. `project.py` rejects background dimensions that differ from the native master; do not relax this invariant for framing.

A separate proposed photo-library-storage design changes asset access and export selection. It is not implemented in this inspected baseline and is not a prerequisite to invent here. At execution, compare the actual baseline to these hashes. If storage has landed, use its canonical asset resolver and export selection/identity rather than revision-relative reads or a competing export scheme. If it remains a proposal, implement against current owners and leave it untouched. Resolve changed interface contracts before code; do not merge or advance another plan through this document.

## Alternatives and decision

1. **Recommended: presentation framing at preview/export.** Keep native editing geometry and saved layers; store one optional layout preset and bind immutable exports to their exact layout. Smallest surface that satisfies the request.
2. Expand the working master and every mask/guide/effect. This would require a new master identity and registration/migration of existing work, with no benefit for adding border space. Rejected.
3. Generative expansion or automatic anatomy completion. Contradicts photographed-detail preservation and introduces unnecessary models/privacy/quality questions. Excluded.

This is an architectural planning task because it introduces persisted presentation metadata and a new export/UI interface. The user explicitly requested the implementation plan and independent review together; both are prepared as a reviewable candidate. Approval to implement remains separate.

## User controls

Add a **Framing and margins** section beside export controls, separate from the native authoring canvas:

- Four labelled whole-pixel fields: Left, Right, Top, Bottom. Defaults are zero; values are nonnegative. Unequal margins move the image within the enlarged canvas.
- An **Equal margins** numeric field and **Set all sides** button. This is convenience input, not a second saved representation.
- **Centre image** redistributes existing total horizontal/vertical padding equally; odd extra pixels go to Right/Bottom. It centres the original image rectangle, not an inferred insect/flower.
- **Reset margins** sets all four fields to zero in the unsaved draft. **Reload saved margins** discards only the unsaved framing form after the existing explicit user action. Neither deletes saved exports.
- **Preview framing** produces a separate, non-authoring RGB8 layout preview. **Save margins** persists the preset. Field edits alone create no revisions, exports or server writes.
- Show output width × height, native image dimensions, unsaved/saved status and preview freshness. Keep a previous preview visibly marked stale until a matching response arrives.
- Existing native export actions stay unchanged. Add **Export framed accepted result** and **Export framed draft**; these consume the explicit current validated form, not a silently selected preset. Unsaved form use is shown, and the exact layout is recorded in the export.

All controls work using keyboard and labelled numeric inputs/buttons; dragging is not required. Disable conflicting writes while busy. Preserve unrelated matting/effect drafts across polling, preview, save, export, reload and errors. Saving a preset is not accepting a photo or a composition.

No aspect-ratio preset, crop tool, rotation, scaling, percent units, automatic centring or new drag mode in this first version. Users can choose asymmetric margins and crop the larger result later. These omissions keep the requested control small and preserve all photographed content.

## Geometry, precision and backdrop

Canonical settings are exactly `{left_px, right_px, top_px, bottom_px}`. Values must be Python/JSON integers (booleans, fractions, NaN, infinities, strings and unknown keys fail). For native width W and height H:

`output_width = W + left_px + right_px`

`output_height = H + top_px + bottom_px`

`source_rect_xyxy = [left_px, top_px, left_px + W, top_px + H]`

The output contains every native pixel exactly once, at integer offset `(left_px, top_px)`, with no resampling. Top-left origin and half-open rectangles remain unchanged. Preset dimensions/identity bind to the oriented developed image; display zoom never enters stored geometry.

Render the native selected result with the current canonical renderer, then copy that finished result into the source rectangle. This is final placement, never feeding a flattened result back as foreground or multiplying alpha again.

For Result margins, use only the **saved backdrop RGB16**: repeat its nearest boundary value outward (including corners), then place the native result in the source rectangle. For legacy absence, use pure black. This preserves the existing complete result byte-for-byte at decoded-pixel level, including partially transparent hairs/web, while adding background only. Do not pad the flattened result by edge repetition: that would stretch legs or petals into the margin. Do not regenerate, resize, reflect or tile the saved backdrop. A varied backdrop may form visible constant edge bands on large extensions; show this in preview and require visual assessment, not a quality guarantee. A future alternative that changes the interior backdrop requires a separate design decision.

RGB16 framed TIFF keeps sRGB profile and exact sample values; RGB8 PNG remains explicitly a viewing copy. Transparent framing, when explicitly selected, inserts zero-alpha black pixels outside the native RGBA8 view and preserves native straight RGB/alpha bytes. Editable native layers and all native review panels remain native-sized. Export metadata explicitly distinguishes native operands from presentation dimensions so an editor can apply the recorded translation.

## Saved preset and compatibility

One optional project-owned `framing.json` contains exactly:

```json
{"schema_version":1,"master_id":"<current identity>","source_dimensions_wh":[6000,4000],"margins":{"left_px":500,"right_px":500,"top_px":500,"bottom_px":500}}
```

Use the current canonical identity name/resolver if the storage migration has landed; do not introduce both master/developed identities. Missing file means zero margins in memory, with no file creation or rewrite on read. Invalid, mismatched or symlinked presets produce a framing-specific error; native editing and native export stay usable. A mismatched preset cannot silently apply to a different source/orientation.

Preset save uses the existing project lock, safe managed-path resolver and atomic JSON writer. Compare the expected preset digest (null means absent) and source identity under the lock before replacing. A stale second client must reload. Failures before replacement preserve the old preset; a failure after replacement, including directory synchronization, may leave the new bytes visible with durability unconfirmed. Re-read the actual preset/digest, report that uncertainty accurately and require reload before another CAS save; never claim rollback or automatically replace/delete the visible file. Photo pointers remain unchanged in either phase. Reject malformed/foreign presets without overwriting them; report their path for explicit recovery. No automatic migration, deletion, settings history/database or recipe-field injection. Changing margins must not change recipe/guidance digests, create a processing revision, invalidate inference caches or move accepted/working pointers. Restoring an image revision retains the source-bound preset; the UI labels it independently. Each previous framed export remains immutable and contains its own layout.

## Export and preview contract

The existing `export_project(..., framing=None)` behavior, filenames and destination remain exact. Framing is explicit opt-in. A framed export is a separate presentation delivery containing only `result_rgb16.tif`, `result_RGB8_VIEW.png`, a compact manifest and README; the explicit transparent variant adds `transparent_RGBA8_VIEW.png`. Native layer export remains a separate existing action. Do not generate a full duplicate editable bundle merely to add margins.

The framed manifest binds source identity/dimensions, revision and manifest digest, acceptance/draft status, canonical margins/output geometry, selected effect/background identities, algorithm `saved-backdrop-edge-padding-v1`, encoding and file hashes. Acceptance language is **“Framed presentation of accepted revision; framing has not been separately accepted”**, or clearly DRAFT for an unaccepted source revision. This feature adds no composition-acceptance mechanism.

Destination identity includes revision manifest digest, canonical geometry, variant selection and framing/encoding algorithm. Use the existing safe publication/collision helper. A repeated complete matching delivery is reused; changed geometry or variants gets a different destination; corrupt/incomplete/colliding existing delivery fails without overwrite. An all-zero explicit framing request may produce the separate compact presentation bundle, but its decoded result must equal the native result exactly. Omitted framing must continue using the legacy path.

Preview is an authenticated, same-origin, read-only POST through the existing local server. Add `revision_manifest_sha256` to each snapshot revision entry, computed from the exact validated persisted manifest bytes, distinct from the recipe/guidance `draft_digest`. The browser obtains this binding from the snapshot, then submits the selected revision/manifest, source identity and layout. Return base64 PNG8 bytes in `png_base64` plus identity/geometry metadata. Decode bytes locally into a PNG Blob and use `createImageBitmap`; do not assign/fetch a data URL or weaken the current Content Security Policy. Close replaced/stale bitmaps. Never alter the existing `/image/...` native-crop routes, `coordinates.js` semantics, assistant inspection metadata or authoring overlays. The separate preview cannot create guides/repairs. A stale response must not replace a newer form/revision preview. Maximum displayed long edge is 1600, no upscaling; dimensions and reduced precision are visible. A nonblocking per-server preview lock permits at most one render at a time, returning busy before image allocation for competing requests; release it on success/failure/disconnect. This is a bounded resource guard, not a queue or worker subsystem.

## Resource limits and failure behavior

Before allocation or staging, reject framed dimensions exceeding 32,768 on either axis or 100,000,000 total pixels. These are proposed conservative first-version bounds, not measured speed/memory guarantees; native exports remain governed by existing behavior. A 100 MP RGB16 result alone is 600 MB, so no full-size float64 padded foreground/alpha/weight arrays are allowed. Use one destination buffer at a time and bounded row scratch for fill/conversion; release previous buffers before another variant. Preview performs bounded sampling directly from native result/backdrop and must not allocate the enlarged native-size canvas.

Use existing `check_space` and its 10 GiB reserve before staged export writes, conservatively allowing the current native-render/export budget plus 16 bytes per output pixel and 1 MiB. Measure actual peak allocations during implementation and raise this estimate if needed; never lower precision or resize silently to fit. Tests exercise limits through validation/allocation spies instead of allocating huge images.

Revalidate source/revision state and any explicitly consumed preset digest before publication under the existing lock. Explicit-form exports do not depend on a subsequently changed preset. Low disk, invalid input, corruption, stale state, busy writers, interruption or serialization failure cannot modify source assets, accepted state or previous deliveries. Keep incomplete staging diagnosable according to existing practice; do not add cleanup automation. No model calls, downloads, external services or private-photo uploads.

## Acceptance and review

Independent tests must verify exact native insertion using non-257 RGB16 samples, partial alpha and nonempty protected regions; correct backdrop-only border/corner values; no generated anatomy at the edge; legacy byte/digest preservation; zero-margin identity; concurrent preset writes; stale preview/export handling; immutable repeated exports; failure before publication; source-native coordinate invariance; and saved-only replay with models unavailable.

Human checks use synthetic spider-like legs/petals touching different sides, plus a user-selected local photo only when authorized. Inspect uniform/varied background joins at native scale, asymmetrical positioning, 1-pixel/odd margins, keyboard flow, error recovery and draft labels. Automated checks do not establish photographic acceptance or accessibility. No new runtime/model inference tests are warranted solely for framing, but the existing relevant deterministic suite must pass once on the settled batch.

## Public references checked 2026-10-19

- [GIMP canvas size](https://docs.gimp.org/3.0/en/gimp-image-resize.html): canvas enlargement and integer placement preserve image scale; supports separating canvas size from resampling.
- [NumPy basic indexing](https://numpy.org/doc/stable/user/basics.indexing.html) and [padding](https://numpy.org/doc/stable/reference/generated/numpy.pad.html), also checked through Context7: slicing/assignment and edge-value semantics; existing NumPy is sufficient. Do not adopt new-version-only APIs or upgrade the pinned dependency.
- [W3C dragging alternatives](https://www.w3.org/WAI/WCAG22/Understanding/dragging-movements) and [labels/instructions](https://www.w3.org/WAI/WCAG22/Understanding/labels-or-instructions): use numeric/buttons as complete operation paths; no conformance claim from source inspection.
