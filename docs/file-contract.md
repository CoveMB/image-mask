# Photo project contract

Storage schema **2** is the only supported project format. Schema-1 projects are
rejected without writes, including lock-file creation; retain them for their
original application version or start a separate new project. No migration or
compatibility tree is provided. The independent portable series preset remains
schema 1; it contains settings, not project identity.

One project contains one untouched source reference and one developed image.
`source.json` records original locator/SHA-256, detected format, original
precision (RAW captured precision unknown), original dimensions/profile hash where
available, applied orientation owner, crop/development decisions, output encoding,
clipping count and developed file hash. Standalone locators are resolved absolute
paths; imported locators are `../original/<camera-name>`, relative to `project/`.
The original remains outside writable assets.

`assets/developed/<developed_id>.tif` is uncompressed RGB16 with embedded canonical sRGB ICC.
Identity is SHA-256 of canonical JSON development/source metadata followed by
contiguous little-endian RGB16 samples. Dimensions alone never establish identity.
RAW orientation is applied by LibRaw; other EXIF transforms are applied once by the
ingest owner. Coordinates begin at the oriented master top-left. Points use
integer pixel indices; boxes are half-open [x0,y0,x1,y1). Guide dimensions and developed identity must match exactly.

`recipe.toml` is typed schema 2 with identity, `guides_file="guides.json"`, editable
notes and named groups. Matting keeps geometry at 1024/256, permits auto/cpu/mps,
color cleanup default disabled/strength .35 (enabled boolean and finite strength
0–1 are supported) and shading disabled/opacity 0. Unknown keys, malformed types or
unavailable processing settings fail visibly. Validation expands with supported
processing features. Prose is never code.
`guides.json` contains schema, identity, dimensions and typed regions; see [guidance](guidance.md).

`state.json` alone owns `working_revision`/`accepted_revision` and
`latest_result_revision` (initially null),
`development_approved`, developed ID and status. A new project is `ready` for mask
preparation without development approval. The Boolean remains compatibility
metadata for optional legacy review; it is not automatically set to true and no
processing, trimap-review or final-acceptance operation requires it. Schema-2 empty
projects with `review_needed` remain valid without rewriting state. Working
revisions still require `review_needed`, or `accepted` when the working and accepted
pointers match. Source/developed/drafts remain validated on reopen and before writes.
Latest records the last successfully generated complete matte/repair/effects result
with no stale enabled effects, independently of current drafts and selection.
Normal generation and successful fresh resume publish working/latest together.
Preparation, stale or failed work, acceptance, restore, explicit review and native
or presentation exports do not advance latest. Restoring A after generating B
retains latest B. Post-replace sync failure reports visible state and uncertain
durability; it never promises rollback.
Trimap and final-photo acceptance are still explicit; neither is inferred.

All writers use `project.project_lock`: stable `.writer.lock`, exclusive
nonblocking OS flock; a competing process gets busy, and readers remain unlocked.
Creation reserves 10 GiB plus estimated writes, stages/syncs/reloads the master,
publishes saved assets and publishes state last. Approval writes/syncs a temporary
JSON and replaces state atomically. No initial assets are overwritten. State temps
and `.initial-*` remnants are never authoritative. Failed creation is refused,
preserved for diagnosis, and retried at a new empty location; resume/automatic
cleanup are unavailable. OS lock release on process death needs no lock deletion.
Keep accepted dependencies outside rebuildable cache. Source changes during ingest
reject publication. Managed symlinks and source/output aliases are refused.

Preparation creates labelled RGB8 proxies and immutable prepared revisions. Native
matting adds alpha, final acceptance and base exports. Optional cleanup and protected
inward shading use the additive effects contracts below. Never use a flattened
preview as a master. The [manual review window](workflow.md) provides native
registration and guide authoring through these shared contracts.

Initial assets/state use atomic create-if-absent hard links within the project filesystem; concurrent externally created files cause a visible collision and remain unchanged. Own staged files may remain as diagnostic hard links and are never authoritative. Updates to existing state use atomic replacement. RAW rejected coefficients use null for non-finite values, recorded shape and an explicit validity flag; finite values remain recorded.


TIFF container recognition belongs to LibRaw, not the first TIFF page or filename.
A RAW may expose an RGB8 thumbnail in IFD0. Only LibRaw's unsupported-format result
while opening permits the ordinary TIFF validator; development/processing failures
after recognition stay errors, including later unsupported-operation errors.
Ordinary TIFF precision/compression/profile rules are unchanged. Known DNG/CFA
containers that LibRaw cannot decode cannot be imported as a developed TIFF.

## Explicit SDR-primary JPEG import

`open SOURCE --project NEW_PROJECT --jpeg-sdr-primary` and configured library
`import SOURCE --subject NAME --jpeg-sdr-primary` explicitly select the ordinary
SDR primary of a supported gain-map JPEG. The default continues to reject
multi-image input. No gain map is applied, no HDR image is reconstructed, and
the complete original JPEG, including its auxiliary payload, remains unchanged.
The master has the primary's original 8-bit precision in an RGB16 container;
ordinary ICC conversion and EXIF orientation still apply exactly once.

This bounded route requires two MPF entries with non-overlapping, complete JPEG
payloads, a baseline primary entry and an auxiliary entry, gain-map namespace
version `1.0` in both XMP packets, and explicit `BaseRenditionIsHDR="False"` in
the auxiliary packet. Missing, contradictory or malformed metadata is rejected.
Each image must have one standard XMP packet; duplicate and extended packets
are unsupported. Pillow-recognized gain-map JPEGs using the conventional `hdrgm`
prefix are supported; other namespace-prefix spellings may be rejected as MPO.
Unlike the general format's optional default, absent SDR-base declaration is not
assumed here. Generic MPO, animation and HDR-base input remain unsupported.
This is SDR selection, not complete HDR-format validation or HDR support.

API callers supply Boolean `development["jpeg_sdr_primary"] = True`.
The option and `metadata.jpeg_sdr_primary` (selected image `0`, image count `2`,
base rendition `SDR`, gain map applied `false`) enter the developed identity and
saved `source.json`. Without the option, existing defaults and identities stay
unchanged. Reopening uses the saved master without decoding again. No saved
project is migrated or redeveloped. Import recovery retains its frozen original
development options; it cannot retrofit this choice into an earlier failed
reservation. Preserve that transaction and use a new standalone project or a
separate configured library for a different development.

The format's primary/auxiliary metadata meanings are defined by the
[Ultra HDR format specification](https://developer.android.com/media/platform/hdr-image-format).

## RAW as-shot white balance

`white_balance="camera"` first uses the existing finite, positive RGB multipliers
exposed by LibRaw. If those are unavailable, a recognized three-channel RGBG RAW
in a classic TIFF DNG container may resolve its recorded `AsShotWhiteXY` instead.
This is a source-metadata conversion, not automatic or daylight white balance.
It is not selected by camera name or filename. Explicit daylight development and
the existing usable-multiplier route retain their prior settings and metadata.

The fallback validates the primary profile's rational fields, chromaticity,
positive analog balance and nonsingular three-by-three matrices. It supports
single profiles, dual profiles interpolated in reciprocal correlated colour
temperature, and DNG 1.6 triple profiles weighted in scaled temperature/tint space.
Each applicable camera calibration is combined with its own colour matrix before
blending. Calibration signatures must match for camera calibration to apply.
Triple-profile lights must be distinct. Standard illuminant chromaticities and
custom `IlluminantData` type-0 xy pairs are supported; custom spectral data and
unrecognized illuminants fail visibly. Both TIFF byte orders are supported.
An explicit `AsShotProfileName` must identify the primary `ProfileName`; selecting
extra or external profiles is unsupported. Duplicate consumed metadata tags,
contradictory `AsShotNeutral`/`AsShotWhiteXY`, incomplete profiles, zero rational
denominators, non-positive camera neutrals and unsupported layouts also fail
before processing. No failure falls back to a thumbnail or silently to daylight.

The fallback passes explicit green-normalized RGBG `user_wb` multipliers to the
existing LibRaw development path, with camera/automatic WB disabled for that call.
It retains the existing demosaic, colour transform, gamma, brightness, precision,
orientation and crop policy; it is not a complete DNG renderer or a reproduction
of the phone's processed JPEG/HDR rendering.

Only fallback-created masters add `metadata.as_shot_white_balance` to `source.json`:

- `source="DNG AsShotWhiteXY"`, `algorithm="dng-as-shot-white-xy-v1"`;
- `white_xy`, applied `multipliers`, `matching_calibration` and normalized
  `calibration_weights`;
- `calibration_illuminants` for multi-profile inputs and `temperature_kelvin`
  for dual-profile interpolation.

The existing `camera_whitebalance`, shape and `camera_whitebalance_valid` fields
still describe what the RAW reader exposed. A false flag can therefore coexist
with a successfully resolved as-shot record. The complete metadata and RGB16
pixels remain bound by the existing master identity. Old masters are reopened
from their saved pixels and metadata without redevelopment or migration. Creating
a different development requires a separate project; existing guides, masks and
accepted outputs cannot be rebound by dimensions alone.


## Configured library and original ownership

Explicit storage TOML owns the library destination and optional existing native
model paths. Relative values bind to the selected file's canonical parent; there
is no config discovery or fallback. Unknown fields and unsafe paths reject before
mutation. Loading/status create nothing. Writes create missing managed directories
with mode0700 and new generated import/project files with mode0600 independently
of umask. Existing permissions, including moved originals and sidecars, are preserved.
Managed components reject
symlinks, dangling links, files and permission conflicts.
Ownership scans in Photos and Inbox/.imports ignore only exact `.DS_Store` entries
identified as regular files without following links; all other unexpected entries fail closed.

The library owns Inbox, Photos, Results Preview and Comparisons. Each imported
`Photos/<frozen-basename>/` contains `original/` and `project/`. Source records retain
schema2 and add `original_filename` and `library={photo_id,folder_basename,sidecars}`;
sidecars have filename/SHA-256 records. Photo ID is P plus the first12 source-hash
hex characters; full hashes determine identity and prefix collisions reject.
Project validation checks this ownership structure without requiring the original
to be available for ordinary saved-asset reopen/replay. No schema/state/revision
transition or migration is introduced.

One stable `.import.lock` holds a nonblocking flock across an entire import/resume,
including published/pending identity checks, preparation, original moves and final
publication. Existing-photo processing retains its project lock. Only explicitly
selected regular same-stem Inbox files move. All inputs, space and device identities
are checked before first move; a complete usable project is prepared through the
canonical decoder/create_project first. Native exclusive same-filesystem moves and
parent syncs preserve destinations; cross-device imports have no copy/delete fallback.
Only a complete validated photo bundle is published under Photos. Imports do not
advance working/accepted/latest state or produce a gallery image.

Private `Inbox/.imports/<photo-id>/import.json` is product recovery state, retained
after completion. Its schema2 `kind="photo-import"` records the full source hash,
frozen photo/folder identity, exact development options, phase and selected filenames,
hashes and sizes. Inbox/original paths derive only from those confined components.
The record survives the exclusive move of its staged `bundle/` into Photos. Each
move syncs the file, both changed parents and the record. Resume validates actual
Inbox/staged/final files rather than trusting phase as proof of movement. Ambiguous,
missing, changed or malformed ownership fails closed and preserves remnants.
Preparation attempts interrupted before bundle publication are retained; explicit
resume can prepare a new empty attempt under the same reservation. No automatic
cleanup or general transaction service exists.

Published duplicates return the validated existing project and preserve the extra
Inbox input. Pending duplicates return the exact recovery record; they never
create a second photo or implicitly resume. Changed config does not relocate a
library; recovery requires its matching original destination. Publication followed
by sync/record failure can leave a complete published photo with uncertain
durability. Resume rechecks actual state and reports it; no rollback is promised.
Originals and recovery records require independent backups. See [library usage](library.md).

## Current Result gallery

Each imported photo has one replaceable `Results Preview/<frozen-basename>.jpg`,
bound to `latest_result_revision`, independently of working selection and acceptance.
Complete non-stale native generation/resume publishes after native state. Configured
reopen or `preview repair PROJECT` repairs pending output; intact output is reused
without writing. Status and viewer polling never repair. Preparation, drafts, restore,
review, presentation presets/previews and exports do not advance the gallery.
Standalone projects have no library gallery.

The gallery uses the canonical saved native Result composition, including saved
spatial fade, its protection and the selected backdrop target. It does not flatten
those appearance settings into source pixels or change native alpha.

The photograph retains native aspect, with integer thumbnail rounding, long edge
at most 1600 and no upscale. Explicit RGB16-to-RGB8 conversion and quality85/optimize
JPEG are lossy; canonical sRGB ICC is included without copied EXIF/GPS/XMP. An 18px
Draft/Accepted revision footer sits outside the photograph. Tiny/narrow photographs
are centred on a canvas at least 360px wide without photographic enlargement.

Project-local `preview.json` uses independent schema1, kind `result-preview` and
encoding `native-result-jpeg-v1`. It binds photo/folder/source/developed identities,
revision/raw manifest hash, label, dimensions, photo rectangle and JPEG hash. A JPEG
comment repeats ownership/layout except its own hash, allowing recovery after JPEG
publication without a receipt. Neither record selects pointers or grants acceptance.
Inspection is bounded to 16KiB records/16MiB JPEG, without native rendering. Foreign,
malformed, symlink/nonregular or multiply-linked JPEG collisions remain preserved.
A missing/stale receipt is recoverable from validated ownership and saved assets.

Writers require the matching configured destination/Photos/frozen-folder/project and
hold the existing project lock; they never acquire the import lock inside it. An
exclusive0600 gallery temporary, file sync, identity/target recheck, atomic replacement
and parent sync precede receipt publication. First creation is exclusive; failed
temporaries remain. JPEG/receipt failure after native completion returns actual
pointers with `preview_pending`; it does not roll back native work.

Before acceptance changes, latest's JPEG must durably become Draft. Failure leaves
acceptance unchanged. Only successful state commit permits promotion, only when
latest equals accepted. State replacement followed by sync failure requires actual
state reread and no promotion or guessed rollback. Promotion/receipt failure leaves
actual acceptance with pending output. Generate/accept B, restore A, then accept A
keeps B's photograph labelled Draft. Conservative Draft is allowed; false Accepted
is forbidden. Native assets, schemas and revision snapshots remain unchanged.

New import proposals reserve `.jpg` within the actual gallery parent's filesystem
component-byte limit before lock/state creation, source moves or duplicate lookup.
Existing longer names and pending imports remain valid and frozen. Native generation
works with pending `name_too_long` and required/available byte counts; repair writes
nothing and acceptance changes stop because Draft demotion cannot publish. No alias,
truncation, rename or migration is performed. A valid duplicate proposal returns its
existing overlong owner; an overlong proposal rejects before lookup. Camera and
sidecar names remain unchanged. See [library usage](library.md).

## Shared raster operands and effective recipes

`manifest.files` maps revision-local text and the small overview to file hashes.
`manifest.assets` maps logical raster roles to `{path, sha256}` references under
project `assets/`. New raster objects are content-addressed PNG/TIFF files;
`assets/developed/<developed_id>.tif` retains the identity-bound developed input.
An identical foreground references that same object with its file hash; it is not
duplicated under a hash filename.
Logical raster names below describe roles, not revision-local physical files.
One canonical resolver validates paths, hashes, role, precision, profile, native
dimensions and registration, with effect/parent semantics checked before warm reuse.
The viewer exposes only its existing authenticated image/mask routes.

Inherited references retain exact encoded bytes. An opacity-only shading change
reuses foreground, alpha, W, support and protection without encoding new rasters.
New or changed operands are published and validated before the complete revision
and state. Failures can retain unreferenced immutable objects and unique stages;
these are preserved, never automatically collected. Accepted work never depends
on processing cache.

A completed matte/repair/effects recipe is the exact effective native recipe: applied cleanup, shading,
exposure, fade and background settings plus inherited effective sections. Exact
consumed draft/request bytes remain in `inputs/`. Only applied root draft sections
are synchronized; unrelated pending values remain editable and block acceptance
when their digest differs. Requests bind consumed inputs; public results identify
current editable `inputs_digest` and immutable `revision_inputs_digest`. Restore
selects effective settings, with explicit draft replacement and recovery when needed.
Presentation presets remain independent small project snapshots; deliveries record
the actual settings used, including unsaved settings.

Published revisions retain text and one bounded `preview.jpg`, never native PNG
panels or precision TIFFs. The JPEG is a labelled reduced RGB8 approximation, with
maximum long edge 1600 and no upscale. Before/after records retain native crop,
origin, displayed dimensions and scale. `panel_boxes_xyxy` locates each panel in
the shared JPEG; the displayed dimensions/scale refer to the named `source` panel.
Native before/after evidence uses matching selected or BASE effect settings on both
sides, including when a stale enabled effect requires BASE comparison.
Use explicit `review` output under
`reviews/` for native PNG evidence; reduced overview pixels do not authorize
native assisted corrections. The separate [current Result gallery](#current-result-gallery)
does not replace revision overviews or native evidence.

## Focused comparisons

`review PROJECT --comparison` explicitly saves a focused RGB8 JPEG sheet and
`manifest.json`. Ordinary `review` and assisted cycle requests still produce native
inspection evidence. Generation never starts a comparison automatically.
The comparison has a maximum 1600-pixel long edge, labelled native-crop rows and
optional separate presentation panel. It is a lossy approximation, never a source
of correction coordinates or photographic acceptance.

Standalone output is `PROJECT/reviews/comparisons/<revision>-<request-sha256>/`.
Configured imported projects use `Comparisons/<photo_id>/<revision>-<request-sha256>/`
under the selected library. Only `comparison_RGB8_VIEW.jpg` and `manifest.json`
are published there. After confirmed publication and the final input check, only
the current call's unchanged reduced intermediates and empty staging directories
are removed. Earlier stages are never collected, including on intact reuse.
Publication or validation failures preserve staging. Cleanup refuses unfamiliar
members, replaced files/directories and symlinks; a cleanup error reports the
durably published comparison separately and retains remaining stage files for
inspection. Requests do not change working, accepted, latest Result, gallery or
draft pointers/settings.

The schema-2 manifest has kind `comparison`, `native_authoring_allowed: false`,
`identity_sha256`, `request`, `files`, `dimensions_wh`, `panel_order`, `crops`,
`presentation` and `native_evidence`. The normalized request captures source and
raw revision identities, draft/authoring digests, state/source manifest hashes,
exact half-open native crop boxes and effective settings, including appearance
staleness. Managed records retain the logical photo ID and frozen folder basename. Crop origins, source
panel dimensions, scales and `panel_boxes_xyxy` describe the displayed sheet.
Presentation records bind the selected revision's raw manifest hash, actual margin
or series settings, algorithm, full output geometry and output-to-display scale.
They do not change native crop coordinates. Both presentation modes use the same
bounded rendering as the manual window.

`--retain-native` additionally retains native PNG evidence in project-local
`reviews/rev-NNN/<hash>/`. The comparison binds the exact after manifest and, for
repairs, its direct before manifest, including their raw SHA-256 values. The
response supplies `comparison_manifest_file`, `reused`, and, when requested,
`native_manifest_file`. Native admission checks real PNG geometry, required views,
unit scales, native origins and member hashes; a correctly rehashed reduced or
presentation record cannot authorize native corrections. Native manifest references
must be nonempty project-relative paths without `..`; admission rejects invalid
references before reserving an assisted repair attempt.

Comparison lookup depends on the captured request, independently of live native
evidence. Reuse validates all bound native dependencies before any native
publisher can run. Missing directories, symlinks, altered manifests/pixels or
foreign evidence stop with the comparison and native locations; the existing
comparison is preserved and the native evidence is not recreated. Restore the
intact bound evidence before retrying. When native publication succeeds but the
comparison publication fails, the reported native evidence remains usable; retry
can finish that unchanged pair. A publication or validation failure after the
directory becomes visible reports completion as unconfirmed; an intact retry
validates the pair and syncs each bound native directory's parent, then the comparison directory's parent,
before reporting success. A repeated sync failure retains that uncertainty and
the visible files. Neither partial completion nor reuse implies human approval.

The optional `--presentation FILE` accepts one JSON object with exactly `mode`,
`developed_id`, `revision`, `revision_manifest_sha256`, and either `margins`
(for `add-margins`) or `settings` (for `match-series`). Copy identities from the
current state and selected revision's raw manifest digest; settings use the
existing [margin](#saved-framing-and-bounded-preview) or series contracts. Stale identities and
stale enabled appearance are refused. This option and `--retain-native` require
`--comparison` and cannot be combined with `--cycle-request`.

## Prepared revisions

`revisions/rev-NNN/manifest.json` records parent, master, complete/kind, input/draft
digests, scope, exact file hashes, candidate names/selection/material policies,
model/package/config/backend/dtype/tensor/normalization metadata and referenced
edit snapshot hashes. `request.json` preserves original request bytes through CLI;
`result.json` stores the outcome and portable logical raster-role names; resolve
them through `manifest.assets`. The
public operation returns resolved absolute shared-asset paths for immediate local inspection.
Prepared recipe/guides are immutable inputs for the next matte or repair; preparation
does not apply pending appearance effects. Completion records the actual inherited
effect settings in its effective recipe. `inputs/` preserves original draft,
state/source record and exact external edits. No private capture is copied.

`trimap.png` is full-master grayscale8 with only 0/128/255. `source_proxy8.png` is
explicitly lower precision than the master. `candidates/` and
`selected_membership.png` are binary object membership, never alpha. `supports/`
contains `support16.png`, categorical `protection.png`, and `lock_values16.png`.
The latter holds bound saved alpha only under the protection mask. An initial
prepare has no `base_alpha16.png`; when a parent supplies alpha/applicable corrected
RGB, preparation inherits their references unchanged. No prepare is final-acceptable.

Every prepare holds the original shared nonblocking writer lock. It validates
current base/master/draft digest, typed guides and
conflicts before inference. Referenced edit files must be project-relative and
free of traversal/symlinks. Original request/draft/external files, parent/lock
manifests and saved assets are checked again before publication. Complete staged
outputs are reloaded, hashed and synced, then a revision is published and state
atomically advances working_revision. The accepted pointer is preserved by preparation.
Changed input fails visibly and preserves newer drafts/current pointers. The request
digest is compared with captured draft bytes, and captured state must match the
authorized state. Input validation runs after temporary JSON fsync immediately
before guide/state replacement, after expensive revision validation finishes.

Typed guide edits publish effective guides after stale checks, so callers need
not apply them twice. Result inputs_digest equals the next root draft digest.
A failed state write can leave a complete orphan revision and a newer editable
draft, while prior working state remains usable. Reopen actual state; do not infer
pointer success from exit alone after a sync error. Application immutability and
cooperative flock do not prevent an unrelated process writing managed assets;
text editors should finish edits before starting a request. No multi-file atomic
filesystem transaction or hostile-writer exclusion is claimed.

Only state owns pointers. A directory name or complete orphan does not make it
working or accepted. Incomplete `.prepare-*` directories are diagnostic remnants,
never inference cache or accepted dependencies. Preparation does not resume and no automatic cleanup is implemented. Matte/repair
resume and saved working-revision restore use these same transaction/identity
owners; complete matte acceptance still validates current state.


Optional per-group `morphology` saves explicit native foreground erosion and
unknown dilation margins without changing schema-2 drafts that omit it.
Requested selected-mask proposals add `trimap_proposal.png` and binary
`proposal_boundary.png`; manifest/result identify their exact groups, candidates,
settings and unreviewed status. They are optional revision assets, so existing
prepared revisions without these assets remain valid. They do not replace typed
`trimap.png`, parent alpha or
human review. See [native morphology semantics](guidance.md#optional-native-morphology-proposal).


## Native matte and acceptance

See [native matting](matting.md) for supported steps. `approvals/rev-NNN-trimap.json`
optionally binds explicit human confirmation to exact current prepared revision,
master, draft, manifest and authoritative trimap hashes. Optional proposals remain
unreviewed. Matting and repair do not require this confirmation. When present, it
is validated and copied into `trimap_approval.json`; without it, neither an approval
record nor that revision asset is created. Effects preserve the asset only when
their parent contains it. Within schema 2, revisions without this optional confirmation remain readable;
older application versions requiring this asset cannot read new unconfirmed mattes.
Matte snapshots current inputs and any supplied confirmation, saves scalar16 alpha,
RGB16 foreground, model/package/backend/padding/tile records and a small same-crop overview. No prepare-only/incomplete/stale candidate can be final-accepted.
`qa.json` records structural/core/lock counts and pending human photographic review;
state's explicit accepted pointer records final acceptance separately.

`foreground_rgb16.tif` starts from the master, carrying only explicitly saved
applicable RGB lock values. Scalar alpha16 has no ICC/gamma. The canonical base
renderer in export.py uses these saved layers without model calls. Accepted revisions
remain intact while newer preparation/matte advances the working pointer.

`reviews/rev-NNN/<crop-and-manifest-hash>/` stores explicitly requested native-crop
review exports, outside the lightweight revision directory. Requested deliveries
use versioned identity paths described [below](#requested-result-deliveries).
Native macOS exclusive rename prevents even
empty concurrent directory collisions from replacing existing files. Filesystems
without exclusive rename support fail visibly. Cooperative locks do not exclude
hostile external writers; finish text edits before processing.

`cache/matte/` contains verified rebuildable tile predictions keyed by master,
input/crop/trimap, model/config/package, backend/dtype/geometry/preprocessing.
An initially present corrupt regular entry is a recomputation miss. Its bytes and
the new diagnostic temporary remain intact, and the tile reports
`cache_publication="skipped_corrupt_existing"`. Symlinks and other nonregular
destinations are errors. A backend switch starts the whole fresh stage in its own
namespace. Accepted layers are outside cache.

New successful predictions are serialized, file-synced and validated, then
published with a same-filesystem exclusive rename and parent-directory sync.
Success leaves one named NPZ with one link and no temporary alias from that attempt.
An arriving destination or failed rename preserves existing names and the temporary.
Failure after rename preserves the named prediction and reports uncertain durability;
there is no rollback or overwrite fallback. Old temporary hard links, corrupt
entries and failed stages remain diagnostic data, never accepted or resume authority.

### Inspecting and clearing processing cache

`cache inspect PROJECT` reads direct children of `cache/matte` and returns eligible
`candidates`, `protected` entries with reasons, integrity `blockers`, `writer_busy`,
`candidate_logical_bytes` and a deterministic `candidate_digest`. Inspection never
creates a cache, backend marker, lock, request, receipt or preview.

Only regular single-link files named `<64-lowercase-hex>.npz` with the canonical
tile format are eligible. ZIP members must use stored (the native producer) or
deflate compression; a mixture of these two methods is supported. Every member's
compression method is checked before decoding any member. BZIP2/LZMA and other unsupported methods,
including previously readable entries, remain protected and are recomputation
misses. Their existing bytes are never converted, replaced or cleared automatically.
Each rerun at an occupied unsupported or corrupt key can repeat inference and retain
another validated `.tile-*` diagnostic with `cache_publication="skipped_corrupt_existing"`.

Admission uses one bounded archive snapshot, checks exactly four physical directory
records before public ZIP metadata allocation, and validates consistent footer,
local-header, payload and descriptor extents. Public metadata reads a separate
in-memory view of those unchanged directory records with a trusted fixed trailer;
its offsets are rebased to the original archive, which still owns payload validation.
This keeps metadata allocation bounded across supported Python 3.12 readers.
Supported ZIP64, descriptor, comment
and prefix forms retain those checks. The compressed archive ceiling is 11,574,336
bytes; decoded NPY members are limited to 8,398,608 bytes for alpha and 1,058,576
bytes for each text member. Actual output length, complete stream termination and
CRC must match before any array allocation. Every deflate/drain call has a positive
remaining-length-plus-one bound; excess output and trailing compressed data reject.

All four NPY headers (versions 1 or 2, at most 10,000 bytes each) are checked before
array allocation from the validated buffers, with pickle disabled. The four unique
members must contain finite float32/float64 alpha,
scalar JSON-object metadata, the matching key and content checksum. Alpha dimensions
are bounded by the native tile size. Backend markers, `.tile-*`, unknown files,
nonregular entries, unsupported compression, malformed arrays and every multiply linked
file are protected.
No recursive cache deletion, alias grouping or automatic cleanup occurs.

`cache clear PROJECT --confirm DIGEST` requires the exact inspected digest and
the canonical project writer lock. Imported projects also require their matching
explicit `--config FILE`, enforced by the public operation as well as CLI.
The digest binds candidate names, hashes, logical sizes, fresh file/link identities,
cache-directory identities and retained project/recovery/permanent context.
All retained published revisions and delivery dependencies must validate.

A completed matte/repair requires intact saved operation/input/dependency hashes,
a matching **published** revision and completion manifest hash, and matching
`progress.json` with `phase="complete"`, `status="review_needed"` and revision.
`completion.json` alone precedes publication and cannot establish completion.
Later draft changes, restore, working-pointer changes or removal of the original
external request file do not undo valid saved completion. Resume keeps its stricter
current-input checks. Unresolved, malformed or unknown requests block clearing.
Typed viewer history must have retained consumption or restore-supersession
evidence. A restore backup alone does not retire pending edits: the published
supersession pointer must match its retained prior pointer. Each resolved edit
batch accounts for one authoring record, preserving exact pointer associations;
identical actions cannot resolve an extra interrupted authoring save. Unprovable
history blocks clearing. Assisted cycles must have a valid stopped hash chain and anchor.

Known `recovery/restore-*` directories preserve prior bytes and a bound target
request. A fully captured backup is protected without implying restore completion;
incomplete or unrecognized captures block clearing. Prior invalid draft bytes remain
opaque backup data. Clearing never repairs or removes any history.

Before unlinking, clear rechecks context and the candidate's path, content, fresh
identity and link count through held real directory descriptors. It repeats context
checks before every later unlink and stops on the first change or failure.
Results report `status`, actual `removed` paths, `removed_logical_bytes`, `failures`
and `durability_uncertain`. Partial removal or parent-sync uncertainty returns a
nonzero CLI exit and preserves the remainder. There is no rollback claim.
Originals, models, shared assets, revisions, presets, deliveries and recovery
diagnostics remain untouched. Logical bytes do not promise physical disk recovery
on copy-on-write or snapshot filesystems.

This is the cooperative local-writer boundary: advisory locks and fresh checks
do not make compare-and-unlink atomic against arbitrary hostile writers.


## Saved scoped repairs and restore

Schema-2 repair revisions extend complete matte revisions; earlier saved matte
and prepared revisions remain readable. Preparation carries parental
`base_alpha16.png` and `foreground_rgb16.tif` unchanged. Repair requires a current
prepared revision with a complete same-master parental matte,
verified immutable ancestry and exact current draft digest. No repeated guide
edits are accepted on a repair request.
Trimap confirmation is optional; any recorded approval is validated. Final
photographic acceptance remains a separate human decision.

Every repair contains `repair/parent_alpha16.png`,
`repair/candidate_alpha16.png`, `repair/support16.png` and `repair/merge.json`.
Scalar operands are full-master grayscale16 PNG. The candidate contains the
quantized native context prediction and parent samples elsewhere. Metadata binds
parent/master/manifest, native half-open context and scope, origin/dimensions at
scale 1, directional policy/rationale and ordered float64 ties-to-even arithmetic.
The existing protection/lock/trimap files are reused. All operands are hashed in
the revision manifest. Replay checks parent bindings and validates its result
against `base_alpha16.png`; accepted/review/export routes use the same check.
Context is part of cropped inference cache identity even if repeated image/guide
bytes would otherwise match a different native crop.

Repair uses the existing foreground/alpha renderer and final human acceptance
control. Preparing/repairing/restoring does not advance final acceptance. Restore
replaces working drafts only under the shared lock and snapshot rechecks;
unsaved text requires explicit `--replace-drafts`. Before any replacement,
`recovery/restore-*/` retains previous recipe/guides/state/source bytes and the
restore request. Preserve these records after interrupted restore. No automatic
deletion or rollback changes an accepted pointer.

Restore also supports existing revisions whose saved guides were normalized while
the draft digest binds the original editable bytes. In that case it restores
the exact hashed `inputs/recipe.toml`/`inputs/guides.json` snapshots only after
verifying their digest and saved target validity. It never substitutes current
mutable text. Default unsaved-edit checks bind the captured bytes, so an edit
between initial inspection and snapshot cannot be silently replaced. Explicit
`--replace-drafts` can recover malformed current draft text; immutable state,
source, master and revision validation remains mandatory.

Without a working revision, default restore requires the current drafts to match
the target revision's draft digest. Different draft bytes require explicit
`--replace-drafts`; they remain preserved in the returned recovery directory.


## Interrupted matte/repair records

`requests/matte-*/operation.json` and `inputs/` retain the original typed request
and exact state/source/recipe/guides snapshots. Their immutable recovery manifest
binds snapshot and consumed parent/support/lock/approval hashes and the original
request file, if supplied. `progress.json` describes calculation progress/errors;
`completion.json` references only a validated complete temporary/published
revision. These records never own working or accepted pointers: `state.json`
remains the sole authority. Within schema 2, these records are optional.
Resume checks dependencies again immediately before publication/pointer replacement.
Accepted data remains outside cache. Complete stage reuse validates the same
revision contract as normal publication; incomplete or corrupt work is retained
for inspection, never promoted by directory presence alone.

Tile cache format v2 also binds the complete identity and exact key inside each
entry. Missing master/model/config/package/dtype/preprocessing identity disables
reuse. `cache/matte/backend.json` selects a backend generation; a device change
abandons the entire previous generation without removing its files. Legacy cache
entries safely miss. Saved accepted layers and exact operand replay are unaffected.


## Local review authoring and exposure

The packaged viewer serves only one explicitly opened project on `127.0.0.1` with
an ephemeral port. Exact Host/Origin and a per-launch capability header protect
private reads and mutations. There is no filesystem URL browser, arbitrary path
endpoint, remote asset or model download. Image URLs bind oriented native crops to
master/revision identity; prepared masks are selected from validated manifest
allowlists and checked against exact saved hashes. The browser inverts zoom, pan,
letterbox and CSS/canvas scaling before recording native coordinates.

`recipe.toml` and `guides.json` keep their existing schema/authority. New optional
`viewer-draft.json` binds saved pending typed edits to master, working revision and
current draft digest, with exact retained `requests/viewer-<id>.json` authoring and
`requests/viewer-edits-<id>.json` shared-edit records. The authoring record retains
the prior recipe bytes as text. Viewer mutations also compare a SHA-256 of the
pending pointer bytes, so same-recipe edits in another browser cannot be overwritten
silently. Pending edits do not become confirmed guides until canonical preparation;
processing/approval rejects unprepared current pending edits. Immutable prepare
`external_inputs` proves consumption, including after a restore of an older identity.
Within schema 2, these optional files appear only on manual save.

Explicit restore preserves previous recipe/guides through the existing recovery
owner. Restore also retains the exact pending pointer bytes in recovery and marks the pointer
`superseded_by_restore`, including same-revision restores. Pending records remain retained separately and can be loaded explicitly for
review if stale; they cannot silently rebind locks or change acceptance. The state
pointer remains the sole owner of working and accepted revisions. No viewer-specific
processing engine or acceptance shortcut exists. UI RGB8/support8/alpha8 images are
viewing approximations, never replacements for authoritative precision layers.

## Optional assisted review history

Schema-2 manual processing requests remain compatible. Prepare/repair optionally accept `assisted_review` as defined by [the assisted workflow](assistant-workflow.md). Immutable `requests/review-<identity>/000-<content-sha256>.json`, `001-<content-sha256>.json`, etc. record the original explicit cycle request, reservations and source comparisons with content-addressed filenames and predecessor hashes. Terminal-byte changes, missing/reordered predecessors, contradictory transitions and lost reservations referenced by retained recovery requests fail closed. A per-cycle `head.sha256` integrity anchor binds the latest event, detecting removal of a valid terminal suffix as well as altered bytes. Events publish before the atomic anchor update; any partial event/anchor publication fails closed and remains retained for inspection. The anchor owns no working/accepted pointers or separate attempt counter. The single project lock serializes writes. This history is advisory, not another working/accepted state authority. A repair reservation is durable before model execution and reused by the same resume request. Two attempts total are shared across all defects; judgement is required between attempts. Stop keeps the best valid revision identity without changing acceptance or restoring drafts. Original prepare/repair requests/results and recovery snapshots retain existing meanings.

Current `review` exports include current working/accepted/draft identities, selected revision draft digest, frozen actual recipe/model settings, authoritative asset paths, structural QA, crop-image hashes and stale/effects labels. These fields are additive; existing RGB8/alpha8 panels, exact native crop origins/scales and full-precision layer contracts remain unchanged. A refreshed manifest receives a new content-addressed directory when current draft/state labels change. Saved revision-local before/after panels describe that operation's immutable comparison; obtain a current `review` export before proposing another correction. Cleanup availability and actual enabled/stale state are explicit; protected inward shading uses the additive contract below.

Each successful native review removes only its own unchanged duplicate staging files or empty outer staging directory after validating durable canonical evidence, required before evidence and current inputs. Canonical manifests and PNGs are rechecked after synchronization and final input checks, before any disposal. Earlier stages, unknown or changed members, replacements, links and failed or uncertain invocations remain for inspection. A late disposal failure may leave some validated duplicates removed; its error identifies the durable canonical evidence and remaining stage. Completed native evidence remains usable if a later comparison or assessment write fails. This lifecycle does not change review identities, rendering, acceptance or existing recovery retention.


## Unchanged effects results

Effects run only on explicit submission. A fully validated repeat of the current
complete effects request returns the same revision/assets with `reused=true`.
New computation returns `reused=false`. The returned `parent` remains that saved
revision's historical parent; `inputs_digest` identifies the current editable
draft, and `revision_inputs_digest` identifies the saved effective recipe/guides.
Reuse never changes working/latest/accepted state or rewrites drafts. Existing
pending draft differences can still block acceptance. Restored working A can be
reused while latest B remains the gallery result. A missing latest gallery may be
repaired by the existing derivative owner, with failure reported as pending.

The additive `effects_reuse` record in an effects manifest and its hash-bound
`result.json` contains `schema_version=1`, `execution`, `request`, `inputs` and
the current `spatial_fade` and `local_sharpening` output bindings (null when absent).
It records the finite effects execution version, Python/package/algorithm versions,
effective request settings/scope/mode/candidate semantics, captured input hashes,
source/native/guides/base-recipe/lock identities. Locator names alone never prove
equivalence. Fresh base/draft identities and all normal permissions, operand,
protection, stale-effect and publication rechecks precede a hit. The original
consumed request/result must bind to this revision and its parent, so inherited
provenance cannot authorize another kind of operation.

Missing, unknown or unsupported reuse provenance computes normally; existing
revisions are not rewritten. Changed protection, scope, authored metadata or
execution identity can create a meaningful small revision even if pixels agree.
There is no historical request search, registry or new cache engine. The explicit
effects execution version must change when equivalence, validation or arithmetic
semantics change. Existing native model/tile cache invalidation stays independent.
Current `validated-effects-v4` covers all seven effects, including Fade into background's
validated nested settings, algorithm, actual explicit protection bytes and all four
saved spatial operands. Its output binding includes OFF and inherited spatial state;
new output is bound only after generation, allowing the first equivalent repeat to
reuse it. Native recipe identity excludes all seven appearance sections. Mandatory cold
saved-geometry validation may rasterize W; a hit performs no additional result/effect/W
generation, while existing warm validation caches retain their fresh-hash safeguards.
Omitted shading-disable geometry still resolves from validated saved settings before
comparison and generation; the original request remains unchanged in diagnostics.
Older v1/v2/v3 proof computes normally once.
The sharpening binding includes its complete saved operands and the cleanup-selected
input: base/corrected RGB, alpha, cleanup record and cleanup dependencies.
Successful reused Reset synchronizes only its matching submitted effect controls
to the returned settings; unrelated controls and independent area drafts remain.
Matching reused spatial Apply clears only its submitted draft; Disable still uses
saved geometry and preserves unrelated or subsequently edited shapes. Explicit Reload
and Cancel retain their existing saved-state behavior.
An actual computation miss captures its request, root input bytes and
`inputs/effects.json` identities/hashes in the existing `.effects-*` stage before
generation; failure retains diagnostics and prior accepted data. This diagnostic
record identifies consumed inputs; the final reuse proof additionally binds generated
spatial and sharpening output. It is not a separate archive of every external
file or a resumable execution checkpoint.
This adds no effects-resume API. Early invalid submissions return errors without
publishing a result or silently consuming drafts.

## Optional source-guided color cleanup

Schema-2 `effects` requests extend the finite `run` operation. Common identity fields
are unchanged. Require `scope_xyxy`, project-relative `support_file` (aligned scalar16),
and boolean `candidate_comparison`. Optional `color_cleanup` overrides the current recipe
section with enabled boolean and finite strength in [0,1]. A complete accepted base
or explicit candidate comparison is required to enable nonzero cleanup. Old requests
and schema-2 projects remain valid; no model setup is needed.

Complete effects revisions retain unchanged `base_alpha16.png` and base
`foreground_rgb16.tif`, plus separate profiled `corrected_rgb16.tif`, canonical
`effects/support16.png`, dependency `effects/alpha16.png`, immutable actual
`effects/settings.json` and the operation's `effects/write_support16.png`. The manifest
hashes every file and records actual strength, enabled/stale state, developed identity,
alpha/support hashes, native scope, algorithm and parent manifest identity. The parent
chain retains prior scoped settings; latest strength describes the latest patch, not
an implicit global rewrite. Cumulative support/dependency maps describe retained layers;
each immutable effects revision retains its exact write support and settings.
Current review exports project `settings.color_cleanup` from the validated saved
manifest's applied enabled/strength values, including inherited effects and zero/off
semantics. Stale enabled cleanup retains those settings; `effects.color_cleanup.stale`,
`cleanup_stale` and the selected base asset identify its temporary exclusion from the
view. Other settings come from the consumed recipe snapshot. The saved `recipe.toml` and `draft_digest` bind effective settings; exact consumed
draft bytes, including any overridden values, remain under `inputs/`.

Nearest confirmed-empty (trimap=0 AND alpha=0) source RGB supplies background;
amount=strength*(1-alpha16/65535)*(support16/65535). Correction is
round(clip((source-amount*background)/(1-amount),0,65535)) in float64 ties-to-even.
Only permitted partial-alpha samples change; opaque, zero-alpha, protected and
outside-support samples remain exact. No true-color or missing-detail recovery claim.
No smoothing width from a historical photograph is imposed globally.

Prepare carries actual cleanup assets; matte/repair compare saved alpha dependencies
and mark enabled cleanup stale. Saved base-to-base repair comparisons disable cleanup
on both sides and label that state. Live viewer comparisons also disable both sides
while the current cleanup is stale. Same-alpha `/image/.../base` explicitly selects
base RGB. Review manifests expose cleanup status and `cleanup_stale` labels. Accept
and export block stale enabled appearance. A prior complete accepted result can still
be exported by its saved identity. Explicit disable selects base master RGB with
applicable saved-value locks; zero strength is equivalent to off.

A rebuild copies prior corrected RGB outside its declared nonzero support, respects
saved RGB locks inside (including partial-alpha values), and updates only covered
alpha dependencies. Remaining uncovered changed alpha keeps the effect stale. Broader
support is never inferred. All prior revisions/assets/accepted exports remain preserved.
Publication uses the existing writer lock, immutable directory publication and atomic
state pointer with rechecks. An interrupted pointer leaves a complete orphan revision
that can be inspected and selected explicitly with restore; no accepted pointer changes.


Effects revisions bind their `draft_digest`, saved recipe and saved guides to
the effective settings. Unapplied notes and other draft sections remain pending;
only explicitly applied settings join that effective snapshot. Changed guidance or mask-affecting recipe sections
require prepare and a complete matte first; effects cannot accept unprepared mask
changes. Valid whitespace-only guide changes retain their exact consumed bytes.

On full matte or repair, applicable saved RGB locks also overlay the inherited
corrected layer. The alpha operation validates its own write support before applying
a different RGB lock; effect-layer selection cannot override that lock afterward.
First enable/re-enable starts unaffected RGB from saved base foreground, including
outside-support locks; correction arithmetic still derives only from the master.
Prepared lock snapshots retain their inherited complete appearance before new guide
requests apply. Valid unchanged-alpha repair comparisons select the same cleanup state
on both sides; stale comparisons continue to select base RGB on both sides.


For a repair, an outside-support RGB lock is compared against the verified saved
selected parent appearance, including current valid cleanup. A lock equal to that
appearance can bind without changing it; a genuinely different historical RGB value
outside support is rejected. The explicit saved lock binds base and corrected layers;
stale comparisons remain labelled base-to-base and represent their actual saved base
layers. Original source/master and prior accepted exports remain unchanged.


## Optional protected inward shading

Schema-2 `effects` retains its common identity, `scope_xyxy`, `support_file` and
`candidate_comparison` fields. `shading` contains boolean `enabled`, finite scalar
`opacity` in [0,1], positive `width_px` no larger than the native image extent,
and `direction_degrees` in [0,360). Direction is clockwise in native coordinates:
0 right, 90 down. Width/direction have no new-photo defaults. Legacy disabled
recipes `{enabled=false, opacity=0.0}` and existing cleanup requests remain valid.
A shading request changes only shading; an explicit cleanup request changes only
cleanup. Simultaneous settings use the declared support for each effect.

Enabling or rebuilding requires an accepted base or explicit candidate comparison,
plus `shading_protection_file`: the saved authored categorical8 PNG (0/255),
or an aligned explicit categorical16 PNG (0/65535). Both normalize losslessly
to saved categorical16 protection. The viewer defaults to the current revision
`supports/protection.png`; author saved-value lock guides, prepare, review the
trimap and complete matte/repair to choose those protected regions locally.
Choose protected hairs, antennae, web, petal tips, genuine highlights and bee
explicitly. This mask combines with saved protection and RGB/alpha locks.
Heuristic thickness/highlight attenuation does not promise semantic protection.
The inward smoothstep uses the alpha >= 0.5 silhouette, an explicitly empty
padded exterior, thickness and directional-normal attenuation, source luminance
and low-alpha attenuation. The reference thickness/smoothing ratios scale with
the chosen band. The reference 48/88px widths and tentative 24% opacity never
become global defaults.

Save `shadow_weight16.png` separately from opacity, with own cumulative support,
alpha dependency, explicit protection and actual settings under `effects/shading/`.
W includes geometry/direction/protection and excludes p, even at p=0. Scoped
rebuild preserves previous W outside its support and keeps previous protection
inside it. Alpha dependency samples update only within that support; remaining
uncovered changes keep the enabled effect stale. Each immutable revision retains
its actual settings and previous complete revisions remain available.
`opacity_only=true` reuses W and geometry exactly; its settings explicitly label
a **global opacity only** operation. Disabling is an explicit global setting,
retains saved geometry/assets, and restores appearance without changing alpha.
Neither shading nor rendering invokes models.

The one authoritative renderer is encoded-sRGB float64
`round(F * (A16/65535) * (1 - p*(W16/65535)))`, ties-to-even. F is saved base
foreground with applicable RGB locks or selected corrected RGB. No intermediate
shaded foreground quantization, flattened-black foreground reuse, second alpha
application or second compositing mode is permitted. Here p is effective opacity:
use saved `shading.opacity` only when `shading.enabled` is true; disabled or absent
shading means p=0 even when nonzero W/opacity are retained for editing. Off/p=0 is identity relative
to the selected unshaded foreground/alpha rendering.

Prepare carries the optional effects; matte/repair recompute their independent alpha
dependency status. Any stale enabled effect selects BASE-to-BASE comparisons,
with all optional effects disabled on both sides and labels stating this. Viewer labels
bind to the successfully displayed revision and effective BASE/stale/opacity
mode; loading or failed images cannot retain misleading appearance labels. Acceptance
and draft appearance export remain blocked until EACH stale enabled effect is
explicitly disabled or independently rebuilt. Prior accepted complete exports
remain usable. Review manifests expose `cleanup_stale` and `shading_stale`.
`/image/.../base` selects all optional effects off; `/image/.../p0`, `/p0.12`, `/p0.24`
compare identical native crops using saved W and selected cleanup, without
changing saved opacity or accepting appearance. Stale comparisons stay base-only.

Exports retain source RGB16, selected unshaded foreground RGB16, base A16,
optional corrected RGB16, unbaked W16 and separate actual effect settings.
Black RGB16 TIFF is authoritative; transparent RGBA8 straight RGB includes
shading but is not alpha-premultiplied, and labels disclose reduced precision
and baked shading. Preferred editable editor handoff is foreground plus alpha
and W+p: mask the foreground group with alpha ONCE, use a solid black layer
with W and chosen p over foreground, and place black background below. No
baked overlay or GIF is generated. If a downstream editor bakes p into overlay
alpha, label that strength and use 100% layer opacity.


## Optional Fade into background

Optional recipe `spatial_fade` has exactly `enabled` (boolean),
`preserve_highlights` ([0,1]), `oval`, `arcs_enabled` (boolean), `arcs` (0–32).
Absence preserves legacy rendering, saved bytes and export members without migration.
Unknown fields, nonfinite numbers, numeric booleans and invalid inactive shapes fail.
Oval fields are exactly `enabled`, `center_xy`, `inner_radii_xy`,
`rotation_degrees`, `transition_width`, `amount`. Arc fields are exactly `id`,
`enabled`, `center_xy`, `rotation_degrees`, `half_span`, `bend`, `fade_side`,
`transition_width`, `end_softness`, `amount`. Arc IDs are unique lowercase UUID-v4.
Centres are continuous native coordinates in `[0,width] × [0,height]`; pixel centres
are `(x+.5,y+.5)`. Rotation is clockwise `[0,360)` on x-right/y-down axes.
Radii, half-span and transition width are `[.5,2*max(width,height)]`; bend is
`[-half_span,half_span]`, end softness `[.5,half_span]`, amount `[0,1]`.
Direction is `positive` or `negative`. UI full width/height/span are twice saved
radii/half-span. Inactive vectors remain validated and independently recoverable.

An exclusive schema-2 `effects` request contains exactly the common
`schema_version`, `kind`, `developed_id`, `base_revision`, `inputs_digest`,
`scope_xyxy`, `candidate_comparison`, plus complete `spatial_fade` and optionally
`spatial_fade_protection_file` when enabled. Scope is the full native rectangle.
No other effect/background fields are permitted. Enable requires an accepted base
or explicit candidate comparison, even for zero/empty geometry. Disable needs only
a valid working revision. The optional project-relative file is aligned categorical
PNG8 (0/255) or PNG16 (0/65535). Old/new explicit protection and saved locks are
unioned; omission/disable cannot remove them. Full settings replacement removes
old arc footprints. Enabling spatial fade disables inward shading and retains its
settings/W; enabling inward shading disables spatial fade and retains its operands.
OFF never revives the other mode. Shadow fade is independent.

The logical roles under `effects/spatial-fade/` are `weight16.png`,
`protection16.png`, `alpha16.png` and `settings.json`. The three rasters use immutable
shared `assets` bindings; revision-local `settings.json` stays in `files`. They hold
combined strength W16, categorical P16, alpha dependency and the complete manifest
record respectively. Readers validate their bound bytes and native registration.
The exact record fields are `schema_version:1`, `enabled`, `settings`, `stale`,
`source_id`, `algorithm:"linear-srgb-oval-arcs-background-fade-v1"`,
`alpha_sha256`, `weight_sha256`, `protection_sha256`, `candidate_comparison`,
`scope_xyxy`. Identity, closed inventory, hashes, dimensions, categorical values,
switches and replayed W are checked even OFF and before successful cache reuse.
Prepare/matte/repair retain operands. Changed alpha makes an enabled record stale;
any stale enabled effect gives labelled all-effects-OFF BASE review and blocks
acceptance/export until explicit rebuild or disable. Corruption fails rather than
silently becoming OFF. Revision publication retains state-last recovery.

Geometry uses cubic `S(t)=clamp(t,0,1)^2*(3-2*clamp(t,0,1))`. Each oval ray
transitions between ellipses with radii `(a,b)` and `(a+w,b+w)`, then stays at 1.
Each ray is monotonic; arbitrary paths across rays need not be. Arc local boundary
is `bend*(1-(u/L)^2)`, signed distance `d=±(v-boundary)`, contribution
`S(d/w)*(1-S((abs(u)-(L-end_softness))/end_softness))`, zero at/beyond `abs(u)>=L`.
Soft ends are lateral; there is no trailing taper. Combine enabled/group-enabled
shapes as `C=max(amount*G)` and quantize once, `W16=round(65535*C)` ties-to-even.
Master OFF does not erase W. Generation holds one W16 plus 64-row geometry scratch,
not full-frame fields for each arc. A weaker arc cannot subtract from an oval.

Selected foreground F includes applicable cleanup, sharpening, exposure and independent Shadow
fade. For alpha-positive, unprotected pixels, `q=W16/65535*(1-p*h(F))`: p is this
feature's highlight setting, h is cubic linear-sRGB luminance weighting using
.2126/.7152/.0722 and thresholds .10/.75. Alpha gates eligibility only. Master OFF,
stale or protection gives q=0. Decode F and selected background B, blend
`(1-q)*F+q*B` in linear sRGB, encode, then compose encoded-sRGB alpha ONCE.
Exact q=0/q=1 preserves F/B. Alpha never changes; the effect may tint or brighten.
Black/gray/white diagnostics still use selected B as fade target. Transparent
straight RGB retains that tint; RGBA8 is reduced precision. Match-series RGBA8
zeros hidden RGB where quantized alpha is zero. Native RGBA8 retains its existing
straight RGB at zero alpha; Add margins preserves that native rectangle and adds
zero RGBA outside it.

With spatial fade enabled (inward shading OFF), Match series samples
`P=R(A*F)`, `A'=R(A)`, `Q=R(A*q)` with the same transform
and kernel. Clamp Q into `[0,A']`; where A'>0 use `q'=Q/A'`, `F'=P/A'`, blend
toward the background generated on the OUTPUT grid, then compose once. There is
no per-arc resampling/blending or scaled native backdrop. Zero fields preserve the
original series contribution exactly. When spatial fade is OFF, q is zero; active
inward shading instead uses the existing `P=R(A*F*H)` path with its saved H factor.

Native editable deliveries add exactly `spatial_fade_weight16.png`,
`spatial_fade_protection16.png`, `spatial_fade_alpha16.png`,
`spatial_fade_settings.json` to the existing conditional inventory.
`foreground_rgb16.tif` stays pre-spatial, already including selected earlier effects.
Alpha, source, background RGB16/settings and other effect operands remain separate.
To reconstruct without the project/models: validate the delivered records and
select the active rendering mode. With spatial fade enabled, calculate q from
foreground/W/protection/settings, blend toward delivered B and compose alpha once.
With spatial fade OFF, q is zero; if inward shading is enabled, use delivered
`shadow_weight16.png` and its opacity to calculate `H=1-opacity*W16/65535` and
`round(F*A*H+B*(1-A))`. Otherwise H is 1. The native manifest/README formula
describes the active mode even when inactive spatial operands are retained.
Do not apply sharpening/exposure/Shadow fade again to selected foreground. For series, use
compact layout/sampling/background metadata and the applicable premultiplied
procedure above; include native H in P before sampling when inward shading is active.
Native recipe and README are editable-handoff material, distinct from compact notes.

Editable delivery is an explicit option in every presentation mode. A spatial
record, including OFF/zero, never opts into a companion automatically. The
[requested delivery contract](#requested-result-deliveries) owns the native
sibling's request identity, exact byte binding, file inventory and conditional
response. Compact presentation folders contain no native editing rasters.

Both phases use one writer lock and validated shared source/foreground/alpha.
They publish sequentially, not atomically as a pair, with exclusive directories,
readback validation, file/directory sync and exact no-overwrite reuse. Native
failure blocks compact publication; later failure may leave valid native-only
output. Errors name visible paths/uncertain durability. Retain evidence and retry
identical inputs; differing/tampered deliveries fail. A partial pair is not success.
Resource admission covers both phases and the maximum estimated allocation envelope;
this is not an available-RAM reservation.
After durable success, only that invocation's byte-verified duplicate stage is
removed. Failed, uncertain and earlier stages remain preserved. A cleanup error
identifies the durably published output and any remaining duplicate-stage files.

Authenticated `POST /api/spatial-preview` takes exactly `developed_id`, `revision`,
raw `revision_manifest_sha256`, native `crop_xyxy`, `view`. Views are `off`,
`combined`, `effective`, `selected`; selected adds `shape_id` (`oval` or an ID in
THAT revision). OFF optionally adds diagnostic `panel`. Unknown/removed IDs and
stale raw identities fail. Responses echo identity and contain labelled PNG8 base64.
Crops keep native geometry. Requests share the nonblocking preview guard and
existing origin/session restrictions. Viewer Apply checks raw identity inside the
writer lock. Pending vectors stay local until Apply; delayed responses cannot
replace newer drafts or display stale decoded maps. Map opacity is display-only.

## Optional local exposure

`local_exposure` is an optional schema-2 recipe section with exactly `enabled`
(boolean) and `ev` (finite number in [-3,3], excluding booleans). Missing means
OFF / 0 EV in memory. Reading legacy recipes does not rewrite their bytes or
immutable revision digests. New projects default to OFF / 0 EV.

An exposure-only schema-2 `effects` request uses the existing master/base/draft
identities, `scope_xyxy` and `candidate_comparison`, plus `local_exposure`. It
cannot also change cleanup or shading. An enabled area rebuild takes exactly one
of:

- `exposure_area`: exactly `regions` and `protection` lists of typed native
  support shapes (stable `id`, `role="support"`, `shape`, geometry and
  `feather_px`). Point, rectangle and stroke use the guide geometry contract.
  Protection feather must be zero. This document is independent of matting guides.
- `support_file`: project-relative scalar16 PNG and explicit
  `exposure_protection_file`: project-relative categorical16 PNG (0/65535) or
  authored categorical8 PNG (0/255), both registered to the complete master.

One adjustment exists per revision. Rebuild **replaces** its previous area and
explicit protection; it never unions old selection silently. Saved guide
protections and RGB/alpha locks remain protected. Declared scope must cover both
the previous and replacement nonzero support, including the area being removed.
An enabled selection must contain eligible pixels. `exposure_amount_only=true`
changes only enabled/EV settings and requires saved area/protection with current
alpha. Disable uses `enabled=false`, retains the area and offers recovery from
stale alpha. Amount-only and disable reject replacement geometry/file fields;
their scope must cover the saved area. Viewer actions use the full-image scope.

Immutable revisions save `effects/exposure/support16.png`, `protection16.png`,
`alpha16.png`, `settings.json`, and `area.json` for authored geometry. Every asset
is revision-hashed. The strict manifest `local_exposure` record contains
`schema_version=2`, enabled/settings/stale, `developed_id`, scope, candidate comparison,
`support_sha256`, `protection_sha256`, `alpha_sha256`, optional `area_sha256`
(null for scalar inputs), and algorithm `linear-srgb-local-exposure-v1`.
The settings asset equals the record. Dependency types, identities, hashes,
dimensions, categorical protection and authored geometry are validated even OFF.
Request, draft, source, parent, area and protection inputs are rechecked before
atomic publication under the canonical writer lock. Accepted state is unchanged.

Selection order is original saved foreground, optional saved cleanup, Local
sharpening, local exposure, optional Shadow fade, then either inward shading or
[Fade into background](#optional-fade-into-background), and alpha composition. For eligible pixels,
decode sRGB to linear RGB, multiply by `2 ** (ev * support16 / 65535)`, clamp to
[0,1], encode to sRGB and quantize once with float64/ties-to-even RGB16.
The sRGB thresholds are .04045 (decode) and .0031308 (encode). Alpha does not
scale the exposure gain. Zero-alpha, zero-support and protected RGB are exact;
alpha never changes. OFF and 0 EV take exact identity paths. Exposure always
starts from the unexposed saved layers and cannot compound on repeated requests.
Saved RGB locks snapshot selected pre-shading RGB, including sharpening, exposure and fade,
and exclude those pixels from subsequent exposure and fade. Prepare/matte/repair retain operands; changed alpha makes
enabled exposure stale until explicit rebuild or disable. Any stale enabled
effect produces a labelled BASE comparison; acceptance/export is blocked.

Review metadata reports `local_exposure_clipping`: `clipped_pixels` counts
eligible pixels with any *unclamped* linear channel above 1; `eligible_pixels`
counts nonzero-area, nonzero-alpha, unprotected pixels. Counts use cleanup-selected
RGB before exposure and before fade; downstream fading cannot hide clipping. These are warnings, not a
quality score or a promise of highlight recovery. A current review also exposes
`local_exposure_stale` and the effect record with clipping. The viewer reuses saved
clipping metadata rather than reprocessing the photograph on every status poll.
`/image/.../exposure-off` recomputes fade from exposure-OFF RGB, retaining saved
cleanup, fade and shading; `/base` disables all optional effects. Source and alpha
panels remain unaffected. Comparison creates no revision.

When exposure is present, native exports with `--variant editable` retain selected `foreground_rgb16.tif`,
`unexposed_foreground_rgb16.tif`, `base_foreground_rgb16.tif`, source/alpha,
`exposure_support16.png`, `exposure_protection16.png`,
`exposure_alpha16.png`, `exposure_settings.json`, and authored
`exposure_area.json` where present. Shading W16/opacity remain independent.
The unexposed export includes selected sharpening after cleanup, before exposure and fade.
Reconstruct by applying exposure once, then optional fade once, then the existing
shading/alpha renderer. The selected foreground already
contains exposure; applying it again would be incorrect. Reduced-precision
views remain explicitly labelled. Restore selects immutable saved inputs without
changing final acceptance; no model inference or download is involved.


## Optional Shadow fade

The optional schema-2 recipe section `shadow_fade` has exactly `enabled` (strict
boolean), `amount` and `preserve_highlights` (finite int/float, excluding booleans,
in [0,1]). Defaults are OFF / 0 / 1. Either this section or `local_exposure` may
be absent independently. Missing means OFF in memory; read/reopen never rewrites
legacy root or immutable recipe bytes. Existing revisions stay recoverable through
explicit restore. Older applications are not promised forward compatibility with
new effect records; preserve a separate pre-extension project for older binaries.
Never strip a new effect record to force an older reader to accept it.

A separate schema-2 `effects` operation uses the common identities,
`scope_xyxy`, `candidate_comparison` and `shadow_fade`. It cannot mutate another
effect. An enabled rebuild takes exactly one area source: `shadow_fade_area`
with the same strict `regions`/`protection` support shapes as exposure, or
`support_file` plus `shadow_fade_protection_file` (registered scalar16 support and
categorical16/8 protection). Stable IDs are unique across both shape lists;
protection feather is zero. Saved guide protection and RGB/alpha locks always
join explicit protection. Rebuild replaces the area and explicit protection;
scope must cover both old and new nonzero support, including removed regions.
`shadow_fade_amount_only=true` changes settings using saved current operands and
rejects replacement fields. Enabled selections need nonempty eligible pixels,
even at amount 0. Explicit disable works without a previous area and with stale
alpha; it retains saved operands. UI whole-adjustment requests use full-image scope.

Fade follows cleanup, local sharpening and local exposure, before encoded-sRGB shading and alpha.
Start every render from unfaded RGB16, never from flattened or previously faded
pixels. Decode normalized sRGB with threshold .04045. In float64, compute linear
luminance `Y = .2126 R + .7152 G + .0722 B`, `t = clip((Y-.10)/.65,0,1)`,
`h = t*t*(3-2*t)`, `w = (support16/65535)*(1-preserve_highlights*h)` and
`gain = 2**(-6*amount*w)`. Multiply linear RGB by gain, encode at threshold
.0031308 and quantize once with ties-to-even RGB16. OFF, amount 0, zero effective
weight, zero alpha, zero support and protected RGB take exact copy paths. Alpha
only gates eligibility; partial alpha does not scale the gain and never changes.
Full amount is at most six stops, not guaranteed black. Full preservation leaves
Y>=.75 exact; saturated low-luminance or dim detail still needs explicit protection.
No detail synthesis, alpha erosion or new compositing mode occurs.

Immutable `effects/shadow-fade/` contains `support16.png`, `protection16.png`,
`alpha16.png`, `settings.json`, and optional `area.json`. Every asset and the
revision's `base_alpha16.png` are manifest-bound, including prepared revisions.
The optional manifest `shadow_fade` record has exactly `schema_version=2`,
`enabled`, `settings`, `stale`, `developed_id`,
`algorithm="linear-srgb-shadow-fade-v1"`, `scope_xyxy`, `candidate_comparison`,
`support_sha256`, `protection_sha256`, `alpha_sha256`, `area_sha256` (null for
scalar input). Settings JSON equals the record. Hashes, types, dimensions,
categorical protection, geometry equality and stale/dependency status validate
even OFF. Unbound area files reject before warm-cache return. Bounded semantic
caches retain no image arrays and never bypass current asset hashing.

Prepare retains operands; matte/repair recompute alpha staleness and union new RGB
locks into protection. RGB locks save the selected pre-shading appearance and
cannot receive fade twice. Changed upstream cleanup/sharpening/exposure settings recompute
luminance from current unfaded RGB; there is no cached tonal mask to rebind.
Changed alpha makes enabled fade stale until explicit rebuild or disable.
Any stale enabled effect disables all optional effects in labelled BASE comparisons
and blocks final acceptance/export. Recover each stale effect independently.
Writes use the shared nonblocking project lock, staged complete revision and
state-last atomic pointer update, with snapshot rechecks before publication and
pointer replacement. Interrupted pointer replacement may retain a complete orphan;
only state is authoritative. Explicit restore/retry preserves accepted work.

`shadow_fade_off=true` in layer selection and `/image/.../shadow-fade-off` in
review retain cleanup, sharpening, exposure and shading. Exposure-OFF retains fade and
recomputes its weighting from exposure-OFF RGB. BASE disables all optional effects.
The UI selects one comparison at a time. Comparison writes no revision.
Reset saves fade OFF / amount 0, retaining area, other effects and pending area edits.

Exports retain selected `foreground_rgb16.tif` (exposure and fade applied once),
`unfaded_foreground_rgb16.tif` (cleanup+sharpening+exposure),
`unexposed_foreground_rgb16.tif` (cleanup+sharpening before exposure and fade),
`base_foreground_rgb16.tif`, source/alpha and all existing exposure/shading operands.
Fade operands are `shadow_fade_support16.png`, `shadow_fade_protection16.png`,
`shadow_fade_alpha16.png`, `shadow_fade_settings.json`, optional
`shadow_fade_area.json`. Replay unexposed -> exposure once -> unfaded -> fade once
-> selected -> encoded-sRGB shading/alpha once. Alternatively render selected RGB
directly with shading/alpha; applying fade again is incorrect. RGB8/RGBA8 views
remain reduced-precision, with baked shading labelled. Retain all dependencies;
saved-only reopen/reconstruction needs no models, original locator or network.

## Saved background appearance

An optional recipe `background` contains exactly `color_srgb` (`#RRGGBB`,
case-insensitive input, uppercase on authoring) and finite numeric `variation`
in [0,1], excluding booleans. New project creation explicitly writes
`#120708` / 0.55. Missing legacy settings remain absent through reads, unrelated
edits and restore; their rendering is uniform black. No schema migration is performed.

Background-bearing revisions bind `background/background_rgb16.tif` in `assets`
and `background/settings.json` in `files`. The optional manifest `background` has
exactly `schema_version:2`, `algorithm:"smooth-tonal-background-v1"`, `developed_id`,
`width`, `height`, `settings`, `background_sha256`, `settings_sha256`. The JSON
file equals the two-key settings. Recipe/record/settings, identity, native shape,
uint16 RGB, sRGB profile and hashes must agree. Unknown, missing or unbound assets
are rejected before cache reuse; current hashes precede bounded semantic caching.
Uniform and black pixels must agree exactly with settings. Nonuniform saved
pixels are authoritative; reading never regenerates the field.

For native x=i/(width-1), y=j/(height-1), with singleton axes zero:

```text
q = .48*cos(2*pi*(.58*x-.72*y)+1.2)
  + .30*sin(2*pi*(1.12*x+.33*y)-.7)
  + .22*cos(2*pi*(.24*x+1.23*y)+.5)
field = (q-mean(q)) / max(abs(q-mean(q)))
```

A zero maximum gives zero field. Float64 generation uses two passes of at most
64 rows, row sums in native order and `math.fsum` over row sums; extrema determine
the full-raster normalization. Decode the tone through the shared sRGB transfer,
multiply linear RGB by `2**(variation*field)`, clamp, encode and round ties-to-even
once to RGB16. Zero variation copies RGB8*257; black is exact zero at all strengths.
There is no crop/viewport normalization, seed or random pattern.

Final Result is encoded-sRGB float64 `round(F*A*H + B*(1-A))`, ties-to-even,
where F is selected RGB16 after cleanup/sharpening/exposure/fade, A=alpha16/65535,
H=1-p*W16/65535 and B is the saved RGB16 backdrop. p is saved opacity only when
shading is enabled, otherwise zero (including absent shading). H applies only to F;
alpha applies once, with no earlier rounding. Black compatibility keeps the
existing arithmetic order. Protected underlying RGB/alpha remain exact while
partial-alpha flattened colour changes with B. Clipping diagnostics are independent.

Schema-2 `kind:effects` accepts exclusive `background` settings with all existing
master/base/draft/candidate identities and full native `scope_xyxy`. It cannot
combine foreground controls, area/support/protection inputs or amount-only flags.
It uses the canonical writer lock, snapshots, rechecks, immutable publication and
state-last pointer. An effective recipe is retained with the revision; its editable
copy is atomically updated before state publication. On interruption, accepted
state stays intact, the draft may differ, and a complete orphan can be explicitly
restored with draft replacement. Newer drafts are never silently overwritten.
Unrelated effects operations inherit exact background assets/settings and preserve
pending background draft differences; acceptance remains blocked until resolved.
Preparation/matting use their selected root recipe; alpha repair does not stale or rebuild B. Existing foreground
stale flags still block acceptance/export. Prepared revisions remain non-acceptable.

Every requested delivery includes `result_rgb16.tif` and `result_RGB8_VIEW.png`.
Native `--variant editable` also includes `background_rgb16.tif`,
`background_settings.json` when saved. Result uses B; optional black and transparent
views retain their meanings. Selected foreground is pre-shading and already
exposed/faded: do not replay these twice. Saved F/A/W/opacity/B reconstruct Result
using the effective-opacity rule above,
without source, models, cache or analytic generation. All RGB16 TIFFs carry sRGB.
Earlier export files remain preserved at their saved paths; current export neither
looks them up nor recreates, migrates or overwrites their format. Existing immutable
reviews are not regenerated on open. Current readers restore prior revisions; old readers
are not promised to understand new records. Retain a prior project/revision for
recovery rather than stripping fields. No automatic cleanup occurs.

## Requested Result deliveries

Default export is exactly five regular files: `result_rgb16.tif`,
`result_RGB8_VIEW.png`, `recipe.toml`, `manifest.json`, `README.txt`. Native output
keeps the full original pixel dimensions, without upscaling or print sizing.
Result follows the selected saved backdrop; absent background means black.
The TIFF is uncompressed processed sRGB uint16. The same-size PNG is RGB8; all
delivered RGB/RGBA rasters embed the canonical sRGB ICC. Scalar16 editing masks
remain exact and carry no ICC/gamma. A larger file container adds no captured detail.

Repeatable `--variant` choices are independent: `black` adds `black_rgb16.tif`
and `black_RGB8_VIEW.png`; `transparent` adds `transparent_RGBA8_VIEW.png`.
Both follow the selected native, Add margins or Match series output geometry.
`editable` does not imply either viewing alternative. In native mode it adds
native operands to that folder. With Add margins (including zeros) or Match series,
it adds a separate native editable sibling, not resampled layers in the primary.
Manual defaults remain compact, including saved spatial OFF/ON records. Final
Codex-assisted exports explicitly request editable in the chosen presentation mode;
intermediate edits remain in the project and do not imply photographic acceptance.
The existing `--framed-transparent` spelling selects the same transparency variant
for explicit margins/series. Canonical variant ordering gives equivalent selections
one identity.

Native editable includes selected pre-shading `foreground_rgb16.tif`, `alpha16.png`,
`source_rgb16.tif`, saved corrected RGB and W16/settings where present, independent
background B/settings, and saved exposure/fade source, unexposed/unfaded, support,
protection, alpha, area and settings operands where present. F already contains
local sharpening/exposure/Shadow fade; never apply them twice. Spatial F remains pre-spatial,
with all four saved spatial operands retained even OFF; use the
[active-mode reconstruction](#optional-fade-into-background). Delivered F/A/W/opacity/B reproduce Result
without the project, original, models or cache using the saved float64 ties-to-even
renderer. A missing backdrop means zero B. Flattened Result is never editable F.
Recovery uses the saved opacity only when the delivered shading record is enabled;
disabled or absent shading means effective opacity zero, regardless of retained
nonzero W/opacity. A missing W means zero. Keep retained editing settings unchanged.

Schema-2 manifests identify `export_version=requested-result-v4`, selected revision,
raw source/revision-manifest hashes, effective recipe hash, explicit draft status,
mode/settings/geometry/algorithm, requested variants, native asset/effect identities,
actual Python/NumPy/Pillow/tifffile encoding versions and profile digest. The
request-record hash identifies `exports/<revision[-DRAFT]>-native-<sha256>/`,
`-framed-<sha256>/` or `-series-framed-<sha256>/`. Each `files` entry records
actual bytes/hash and raster dimensions/precision/mode/profile. The frozen recipe
comes from that revision, never the mutable root draft. Notes contain no timestamps
or capture paths. Inference provenance stays bound through the raw revision hash.
Version 3 retains the effective-opacity recovery rule and adds current spatial
identity/operands and explicit optional sibling delivery. Unversioned, v1 and v2
files remain preserved at their existing paths; no legacy lookup, recreation,
migration or rewrite is performed.

For presentation+editable, the native child is a native requested delivery with
`requested_variants=["editable"]`, independent of presentation geometry and its
black/transparent choices. Before any producer, selection, allocation or staging,
build its pure request and deterministic directory, then include only
`editable_companion_request={identity_sha256,directory_name}` in the primary's pure
request. Neither directory lookup depends on existing child bytes. The primary
manifest additionally requires `editable_companion` with exactly `directory_name`,
`manifest_sha256`, `files_sha256` (every child member except manifest, including
README). These actual byte bindings and both `files` tables are strictly validated;
they do not enter the primary lookup hash. Unexpected/missing binding fields fail.
Return JSON adds exactly `{directory,manifest_file,manifest_sha256}` beneath
`editable_companion`. Keep both folders and their names for portable editing.

A present primary with an entirely absent, corrupt, mismatched or symlinked child
fails before either producer; it never recreates that child. An exact native-only
partial may be reused before producing its missing primary. Both absent permits
native-first publication after paired admission; both intact permits no-render
full-pair reuse with exact binding/status/source rechecks and parent sync. A
primary that is itself invalid is preserved. The pair publishes sequentially, not
atomically: later failure can leave a usable native-only partial or visible output
with unconfirmed durability. Preserve named outputs/failed stages and retry the
identical request; do not overwrite or silently repair damaged pairs.

The project lock covers capture, authorization, native operand validation, member
validation and publication. Default selects retained acceptance even with newer
working/latest revisions. Explicit unaccepted output requires revision plus draft;
explicit draft stays labelled DRAFT even for an accepted revision. Root drafts,
presets and unrelated pointers do not change a frozen effective delivery request.
Current acceptance/stale flags, expected source/raw revision and all saved operands
are checked anyway; raw state/source/revision are rechecked before return/publication.

An intact exact matching delivery validates before renderer/effect application,
full composed-output allocation, pending-write admission, exports creation or staging.
Validation still reads native saved operands and may replay scalar repair/layout
calculations. Existing delivery rasters use streaming hashes and TIFF/PNG headers,
not full decoded output arrays. Exact canonical metadata/member sets, file sizes,
bit depth, channel layout, profiles and before/after file signatures must match.
Missing, changed, hidden extra, directory, FIFO or symlink members fail preserved;
they are not replacement cache misses. This cooperative local trust boundary is not
an authenticity guarantee against an attacker rewriting files and their hashes.

Fresh requests retain the 10 GiB reserve, native allowance and selected output
budget; alternatives/readbacks are processed sequentially. Intact reuse syncs the
parent without creating a duplicate stage. A genuine late identical collision may
dispose only of this attempt's fully verified duplicate after durable reuse and
final checks. Exclusive no-overwrite publication, visible durability uncertainty,
failed-stage preservation and mode-specific recovery below remain in force.
No acceptance, gallery, native revision, draft or preset changes result from export.

## Framed presentation exports

`export PROJECT --margins LEFT RIGHT TOP BOTTOM [--framed-transparent]` adds a
separate presentation delivery. Omitted margins retain the native export contract
and file set. Explicit zero margins still select a compact presentation.
Each margin is a nonnegative integer in native pixels. Output width/height must
each be at most 32768 and their product at most 100,000,000; requests are checked
before staging or expanded raster allocation. Native dimensions, editing
coordinates, saved layers, acceptance and project schema do not change.

The canonical saved renderer completes the native Result once, including selected
cleanup/sharpening/exposure/fade, shading and alpha. Framing copies those RGB16 samples without
resampling at `(left, top)`. Outside that rectangle, only the saved native backdrop's
nearest edge/corner pixels extend outwards; legacy backdrop absence means black.
No foreground edge is stretched and no larger analytic backdrop is regenerated.
The optional straight RGBA8 view retains the canonical native viewing samples and
has zero RGB and alpha outside. All delivered rasters carry the canonical sRGB ICC
profile; TIFF is uncompressed processed RGB16, PNGs are reduced-precision views.

The flat directory `exports/<revision[-DRAFT]>-framed-<full-sha256>/` uses the
[requested member set](#requested-result-deliveries), including recipe and opted-in
black/transparent variants, with no editable native rasters.
The schema-2 manifest has kind `framed-presentation`, master/revision identities,
exact validated revision-manifest byte hash, source/output dimensions, margins,
half-open `source_rect_xyxy`, algorithm `saved-backdrop-edge-padding-v1`,
encoding/profile/variant identities, selected effect/backdrop identities and
project-relative native-asset hashes. Its `files` records hash every delivered
member except the manifest itself, with raster dimensions and precision.
The directory identity hashes the canonical manifest inputs before delivered-file
records are added. The bundle excludes capture paths, model configuration and
editable native rasters; keep the local project for further editing. When editable is
explicitly requested, also keep the [native companion](#requested-result-deliveries).

The accepted-source label is “Framed presentation of accepted revision; framing
has not been separately accepted”. Explicit `--revision ... --draft` produces
“DRAFT - explicit framed presentation”, even when that source revision is accepted.
No new photographic acceptance is inferred.

The canonical writer lock covers source selection through publication. Captured
raw state and revision-manifest bytes must correspond to canonical validated
objects; source identity, bytes and saved assets are checked again before publication.
Stale enabled effects fail instead of exporting a BASE fallback. This cooperative
lock does not provide an atomic snapshot against hostile external writers.
Identical complete deliveries are reused; differing, missing, extra, symlinked or
directory members are rejected without overwrite. Files and directories are synced
before exclusive publication. A failed parent sync can leave a complete visible
delivery with unconfirmed durability; identical retry validates and syncs it.
Normal intact reuse creates no stage. If a byte-identical destination appears
during fresh work, only that attempt's verified duplicate stage is removed after
successful validation, final input checks and parent sync. Failed exports retain any unpublished stages;
failed reuse validation or parent sync retains its duplicate stage. A cleanup
failure reports that publication succeeded and identifies the stage for inspection;
some stage files may already be removed. Earlier stages and prior deliveries are
never swept by an export retry.

Resource admission retains the 10 GiB disk reserve and adds the existing native
allowance plus 16 bytes per output pixel, another 10 when black is selected, and
2 MiB. Expanded variants/readbacks are
processed sequentially; RGB8 conversion uses one row of float64 scratch and PNG
readback hashes decoded rows. Admission is a disk-capacity estimate, not a RAM
estimate/reservation or a guarantee that every supported size fits current memory.


## Saved framing and bounded preview

Optional `framing.json` is an independent schema-2 source preset. It contains exactly
`schema_version: 2`, `developed_id`, `source_dimensions_wh: [width, height]` and `margins`
with `left_px`, `right_px`, `top_px`, `bottom_px`. Dimensions and margins are strict
JSON integers; booleans, fractions, negatives, extra fields and foreign source or
dimensions fail. Metadata is bounded to 16 KiB and symlinks are rejected. Absence
means in-memory zeros and a null digest, with no write. Invalid presets produce an
independent viewer framing error; native project operations and explicit valid
preview/export margins remain available. Invalid files are never silently repaired.

The shared project writer lock covers save validation and atomic replacement.
`framing-save` compares the raw-byte SHA-256 last loaded by the client; null means
absent. Even semantically identical external rewrites invalidate that comparison.
Saving an unchanged valid preset retains its exact bytes. Saves do not modify
recipes, guidance, model/tile caches, revision manifests or working/accepted pointers.
Restore retains the source preset; existing exports retain their own frozen layout.
Failures before replacement retain old bytes. A failed directory sync after replacement
can leave new visible bytes: the action reports durability uncertainty, rereads visible
margins/digest when possible, preserves the form and requires explicit Reload saved
margins before another save. No rollback is claimed.

Each validated viewer snapshot revision entry supplies `revision_manifest_sha256`,
the SHA-256 of the exact validated saved manifest bytes, independently of
`draft_digest`. Authenticated same-origin `POST /api/framing-preview` accepts only
`developed_id`, `revision`, `revision_manifest_sha256` and `margins`. It requires a
complete saved result and rejects stale enabled effects rather than rendering BASE.
Source/state/manifest identity is checked again after rendering. The response echoes
all request identity fields and returns `png_base64`, source/output/display dimensions,
`source_rect_xyxy`, algorithm and a reduced-detail label. It writes no project state.

The preview samples the virtual enlarged canvas directly from the completed native
result and saved backdrop, using pixel-centre nearest-neighbour sampling, bounded
row scratch and a display no larger than 1600 on its longest edge. It never allocates
the enlarged full canvas; native saved-result reconstruction still needs native-sized
arrays. One nonblocking render guard per server rejects overlapping render work as
busy, without a queue, and releases on success or failure before HTTP transport.
The page decodes PNG bytes through a local Blob and `createImageBitmap`, displays
only a matching source/revision/raw digest/all-margin/request-sequence result, and
closes rejected or replaced bitmaps. The existing CSP remains unchanged. This canvas
has no native guide-authoring handlers and its pixels cannot define native edits.

## Fixed-size series settings and deliveries

Match series is a separate resized presentation mode. Existing native exports,
exact Add margins samples/identities, `framing.json`, project-state schema, masks,
guidance/recipe digests, coordinates and working/accepted pointers retain their
contracts. Opening a schema-2 project without series metadata creates none; schema-1 projects are refused without writes.

A portable preset is bounded UTF-8 JSON, at most **16384 bytes**, with exactly:

```json
{
  "schema_version": 1,
  "kind": "series-framing-preset",
  "name": "Portrait series",
  "output_width_px": 4000,
  "output_height_px": 5000,
  "side_margin_tenths_percent": 150,
  "minimum_vertical_margin_tenths_percent": 50
}
```

Schema/version/kind are exact. Dimensions are positive strict JSON integers, at
most 32768 per axis and 100000000 pixels total. Both margin fields are strict
integers in `[0,450]`: 150 means 15.0% on **each** horizontal side; 50 means 5.0%
on **each** vertical side. Booleans, fractional integer fields, duplicate/unknown/
missing keys, nonfinite numbers and malformed UTF-8 are rejected. The name is
nonblank valid Unicode text, 1–80 code points, preserved as text. It is never a
filesystem name or HTML. No source identity/path, image, mask, photograph metadata
or background override is included. Readers consume at most 16385 bytes; CLI and
managed preset paths reject symlink aliases and nonregular files.

The browser file picker sends bounded raw text to authenticated same-origin
`POST /api/series-preset-validate` as exactly `{preset_json: str}`. The server
returns validated `settings` and canonical `preset_json`; it accepts no filesystem
path. Download uses a local Blob and fixed filename `series-framing-preset.json`,
releasing its object URL afterward. Initiating download does not establish that
the browser saved a disk file and never saves a project. Valid Load changes only
the form; cancellation, invalid data or a superseded response changes no settings.

Optional project `series-framing.json` contains exactly `schema_version: 2`,
`developed_id`, `source_dimensions_wh: [width,height]` and `settings`, where settings
is the five-field settings object above without portable schema/kind. It has the
same 16 KiB bound. Absence returns in-memory defaults/null digest without a write.
Invalid metadata remains preserved; only the affected series persistence flow is
disabled. Explicit save takes the shared project lock, validates source identity
and uses raw-byte SHA-256 CAS with rechecks before atomic replacement. Semantically
equal external byte rewrites invalidate CAS. An unchanged valid save preserves its
exact bytes. Failures before replace preserve old bytes; post-replace uncertainty
reports actual visible settings/digest when readable, retains form edits and requires
explicit reload. No rollback is claimed. Portable changes do not change saved
snapshots or deliveries. Restore retains source-bound series settings.

Bounds include every saved `base_alpha16` sample greater than zero. The empty mask
blocks the mode. Layout uses one continuous pixel-edge transform with uniform
scale `min(W*(1-2*m)/bounds_width, H*(1-2*v)/bounds_height)` and centred translation.
Integer support envelopes do not define a second scale; reported margins describe
the continuous transformed original bounds, not the first nonzero filtered pixel.
Height-limited fits report wider sides. Source-edge contact warns about clipped
detail; no outlier removal, subject detection, rotation or new photographed detail occurs.

Canonical saved-layer selection supplies cleanup, sharpening, exposure and Shadow fade;
saved shading and alpha apply once. Stale enabled effects block. The renderer uses
encoded-sRGB float64 contribution arithmetic, then separable Pillow scalar `F`
(float32 storage) Lanczos passes over explicit transparent support. All colour/
alpha planes share the same fractional mapping and scale-dependent support.
Exact unit-scale integer placement bypasses filtering. Nonfinite results fail;
alpha is clamped to `[0,1]` first, then each premultiplied channel to `[0,65535*A]`.
Composition is `P+B*(1-A)` with one ties-to-even RGB16 quantization. Transparent
output unpremultiplies only where A is positive, quantizes straight RGBA8 and zeros
RGB wherever its **quantized** alpha is zero. Native protected values stay unchanged
on disk; resized output samples are not promised native bit identity.

The selected saved background recipe/algorithm/hash bindings are validated before
regeneration at final output dimensions. Unsupported algorithms fail. Legacy absence
means black. Regeneration changes backdrop placement beneath partial-alpha edges too,
without rewriting the native saved backdrop. Reduced previews sample the canonical
full-output background grid using its full-width, 64-row, ordered float64 sums and
`math.fsum` statistics; they do not normalize on a different preview grid. Preview
sampling is approximate and bounded to 1600 pixels on the long edge, while the
normalization pass still has output-size-dependent computation.

Snapshots expose independent `series_settings`, `series_digest`, `series_error`.
`POST /api/series-preview` takes exactly `developed_id`, `revision`,
`revision_manifest_sha256` and visible validated `settings`. It echoes those fields,
full layout, full/display dimensions, algorithm, reduced-preview label and `png_base64`.
The source/state/raw revision and validated saved assets are checked before/after
rendering. Both preview modes share one nonblocking guard; no queue or simultaneous
expensive preview is added. Existing token/origin/body guards and CSP remain intact.
The canvas cannot author native guides. Delayed/replaced bitmaps are closed; changes
to source, revision, settings or mode invalidate the preview.

`series-export` binds the explicit selected revision and expected master/raw manifest
identities, plus settings, `draft` and `transparent`. Accepted delivery requires that
selection still be accepted under the writer lock and before publication; explicit
draft remains DRAFT. CLI `--series-preset PATH` may capture its target under lock,
with existing default-accepted/explicit-draft rules, and is exclusive with `--margins`.
No mode silently saves visible settings or substitutes a different revision.

The flat directory `exports/<revision[-DRAFT]>-series-framed-<full-sha256>/` uses
the [requested member set](#requested-result-deliveries), including frozen recipe
and independent black/transparent variants, with no editable native rasters.
The schema-2 manifest kind is
`series-framed-presentation`; algorithm is `series-lanczos-premultiplied-v1`.
Its identity binds full settings/layout/sampling, exact validated source-record and
revision-manifest byte hashes, master/native-asset/effect/background identities,
Pillow version/filter/float-box/rounding policy, encoding/profile and variants.
Delivered members have exact hashes/dimensions/precision records; no personal paths,
capture metadata or editable native rasters ship. Notes label resampling,
enlargement, final-size backdrop regeneration and absent separate composition acceptance.

Shared compact export publication retains validation, exclusive no-overwrite
publication, exact identical reuse, durability diagnostics and the repaired
duplicate-stage cleanup contract above. Only the current byte-verified duplicate
after successful reuse/parent sync is disposable; earlier/failed stages are preserved.
Resource geometry/coefficient/allocation checks precede staging or expanded allocation,
with the existing 10 GiB reserve plus pending-write allowance. Estimates include
retained inputs, output, alpha, scalar intermediate, strip/coefficient and encoding
scratch. They are not RAM reservations or guarantees that every valid size fits.


## Optional local sharpening

Schema-2 recipes may contain `local_sharpening` with exactly `enabled` (boolean),
`amount` [0,1], `radius_px` [0.5,8] and `noise_threshold` [0,0.02].
Numbers are finite int/float, excluding booleans. Absence reads as OFF with defaults
false/0/1/0.001 without rewriting old bytes. Schema-1 policy is unchanged.

A schema-2 `kind:"effects"` request uses the common developed/base/draft identities,
scope and candidate-comparison fields. Local sharpening is exclusive. Enabled
replacement requires exactly `sharpening_area` (typed regions and hard protection)
or `support_file` plus `sharpening_protection_file`. `sharpening_amount_only:true`
uses saved geometry; disable and amount-only cannot replace it. Scope contains both
old and replacement support. Saved guide/RGB protections are merged, never dropped.

The schema-2 `local_sharpening` record binds enabled/settings/stale/developed ID,
algorithm `linear-srgb-local-sharpening-v1`, full alpha/support/protection/optional
area SHA-256, scope and candidate-comparison status. `effects/sharpening/` contains
support16.png, categorical protection16.png, alpha16.png, settings.json and optional
area.json. Registered asset shapes bind native dimensions. All dependencies and
authored/scalar equivalence are validated even OFF; unbound area files are rejected
before warm validation. Unsupported versions and algorithms fail explicitly.

Rendering starts from current cleanup-selected RGB16, decodes float64 linear sRGB,
and forms Y=0.2126R+0.7152G+0.0722B. The mean is G(Y*A)/G(A), A=alpha16/65535,
with Gaussian sigma radius_px, reflect boundaries and integer radius ceil(4*sigma).
Soft-thresholded detail is multiplied by amount and support16/65535. Only nonzero
alpha/support, unprotected pixels are writable. Target Y is bounded by valid
nonzero-alpha 3×3 luminance extrema, then a common RGB gain is limited to gamut.
Y=0, zero denominator/adjustment, OFF and zero Amount preserve exact samples.
Alpha weights context, not write strength. Changed RGB encodes/quantizes once with
float64 ties-to-even. Full-width strips retain the full kernel halo and write only
core rows; previews crop the native result and use this same kernel.

Order is cleanup → sharpening → exposure → Shadow fade → shading or spatial fade →
alpha/background composition. New selected-RGB locks are protected from reapplication;
their captured values become part of subsequent neighborhood context. Alpha changes
make enabled sharpening stale, blocking acceptance/export until whole-adjustment
rebuild or Reset. Prepare/matte/repair, restore, processing-cache context and gallery
use the same validated inherited records. Effects publication retains writer locking,
input rechecks, complete staged revisions and state-last pointers.

Editable native deliveries add `unsharpened_foreground_rgb16.tif` (cleanup-selected)
and `sharpening_support16.png`, `sharpening_protection16.png`,
`sharpening_alpha16.png`, `sharpening_settings.json`, plus
`sharpening_area.json` when authored. Unexposed RGB includes sharpening; unfaded RGB
includes sharpening/exposure; selected foreground includes all three. Replay from
one appropriate starting layer; never sharpen selected RGB twice. Framed/series
editable companions bind these same native operands. Export variants stay independent.

New sharpening records require the updated reader. Older binaries have validation
bypasses and are not guaranteed to reject or correctly render them. Preserve
pre-feature projects/exports for older applications; no automatic stripping,
migration, cleanup or photographic acceptance is performed.
