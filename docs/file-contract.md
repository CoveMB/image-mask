# Photo project contract

One project contains one untouched source reference and one developed master.
`source.json` records original resolved path/SHA-256, detected format, original
precision (RAW captured precision unknown), original dimensions/profile hash where
available, applied orientation owner, crop/development decisions, output encoding,
clipping count and master file hash. The original remains outside writable assets.

`masters/<master_id>.tif` is uncompressed RGB16 with embedded canonical sRGB ICC.
Identity is SHA-256 of canonical JSON development/source metadata followed by
contiguous little-endian RGB16 samples. Dimensions alone never establish identity.
RAW orientation is applied by LibRaw; other EXIF transforms are applied once by the
ingest owner. Coordinates begin at the oriented master top-left. Points use
integer pixel indices; boxes are half-open [x0,y0,x1,y1). Guide dimensions and master identity must match exactly.

`recipe.toml` is typed schema 1 with identity, `guides_file="guides.json"`, editable
notes and named groups. Matting keeps geometry at 1024/256, permits auto/cpu/mps,
color cleanup default disabled/strength .35 (enabled boolean and finite strength
0–1 are supported) and shading disabled/opacity 0. Unknown keys, malformed types or
unavailable processing settings fail visibly. Validation expands with supported
processing features. Prose is never code.
`guides.json` contains schema, identity, dimensions and typed regions; see [guidance](guidance.md).

`state.json` alone owns `working_revision`/`accepted_revision` (initially null),
`development_approved`, master ID and status. A new project is `review_needed`;
explicit approval becomes `ready`. This never accepts a final photograph. Approval
requires the identity the human actually inspected. Source/master/drafts are
validated on reopen and before approval. There is no assistant auto-acceptance.

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

Initial assets/state use atomic create-if-absent hard links within the project filesystem; concurrent externally created files cause a visible collision and remain unchanged. Own staged files may remain as diagnostic hard links and are never authoritative. Approval alone uses atomic replacement of existing state. RAW rejected coefficients use null for non-finite values, recorded shape and an explicit validity flag; finite values remain recorded.


TIFF container recognition belongs to LibRaw, not the first TIFF page or filename.
A RAW may expose an RGB8 thumbnail in IFD0. Only LibRaw's unsupported-format result
while opening permits the ordinary TIFF validator; development/processing failures
after recognition stay errors, including later unsupported-operation errors.
Ordinary TIFF precision/compression/profile rules are unchanged. Known DNG/CFA
containers that LibRaw cannot decode cannot be imported as a developed TIFF.


## Prepared revisions

`revisions/rev-NNN/manifest.json` records parent, master, complete/kind, input/draft
digests, scope, exact file hashes, candidate names/selection/material policies,
model/package/config/backend/dtype/tensor/normalization metadata and referenced
edit snapshot hashes. `request.json` preserves original request bytes through CLI;
`result.json` stores the outcome and portable revision-relative asset paths. The
public operation returns resolved absolute paths for immediate local inspection.
Recipe/guides are immutable effective inputs; `inputs/` preserves original draft,
state/source record and exact external edits. No private capture is copied.

`trimap.png` is full-master grayscale8 with only 0/128/255. `source_proxy8.png` is
explicitly lower precision than the master. `candidates/` and
`selected_membership.png` are binary object membership, never alpha. `supports/`
contains `support16.png`, categorical `protection.png`, and `lock_values16.png`.
The latter holds bound saved alpha only under the protection mask. An initial
prepare has no `base_alpha16.png`; when a parent supplies alpha/applicable corrected
RGB, preparation copies those bytes unchanged. No prepare is final-acceptable.

Every prepare holds the original shared nonblocking writer lock. It validates
human development approval, current base/master/draft digest, typed guides and
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
unknown dilation margins without changing schema-1 drafts that omit it.
Requested selected-mask proposals add `trimap_proposal.png` and binary
`proposal_boundary.png`; manifest/result identify their exact groups, candidates,
settings and unreviewed status. They are optional revision assets, so existing
prepared revisions without these assets remain valid. They do not replace typed
`trimap.png`, parent alpha or
human review. See [native morphology semantics](guidance.md#optional-native-morphology-proposal).


## Native matte and acceptance

See [native matting](matting.md) for supported steps. `approvals/rev-NNN-trimap.json`
binds explicit human confirmation to exact current prepared revision, master, draft,
manifest and authoritative trimap hashes. Optional proposals remain unreviewed.
Matte snapshots that confirmation and the current inputs, saves scalar16 alpha,
RGB16 foreground, model/package/backend/padding/tile records and same-crop review
assets. No prepare-only/incomplete/stale candidate can be final-accepted.
`qa.json` records structural/core/lock counts and pending human photographic review;
state's explicit accepted pointer records final acceptance separately.

`foreground_rgb16.tif` starts from the master, carrying only explicitly saved
applicable RGB lock values. Scalar alpha16 has no ICC/gamma. The canonical base
renderer in export.py uses these saved layers without model calls. Accepted revisions
remain intact while newer preparation/matte advances the working pointer.

`reviews/rev-NNN/<crop-and-manifest-hash>/` stores additional native-crop review
exports; immutable revision review assets remain unchanged. `exports/rev-NNN/` is
accepted delivery, `exports/rev-NNN-DRAFT/` explicitly unaccepted/labelled. Actual
existing bytes must match for reuse. Native macOS exclusive rename prevents even
empty concurrent directory collisions from replacing existing files. Filesystems
without exclusive rename support fail visibly. Cooperative locks do not exclude
hostile external writers; finish text edits before processing.

`cache/matte/` contains verified rebuildable tile predictions keyed by master,
input/crop/trimap, model/config/package, backend/dtype/geometry/preprocessing.
Malformed/unknown entries miss. A backend switch starts the whole fresh stage in
its own namespace. Accepted layers are outside cache. Retained temporary hard links
and failed-stage directories are diagnostic, not accepted or resume authority.


## Saved scoped repairs and restore

Schema-1 repair revisions extend complete matte revisions; earlier saved matte
and prepared revisions remain readable. Preparation carries parental
`base_alpha16.png` and `foreground_rgb16.tif` unchanged. Repair requires a current
human-reviewed prepared revision with a complete same-master parental matte,
verified immutable ancestry and exact current draft digest. No repeated guide
edits are accepted on a repair request.

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
remains the sole authority. Older projects need no migration; records are optional.
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
Older projects need no migration; these optional files appear only on manual save.

Explicit restore preserves previous recipe/guides through the existing recovery
owner. Restore also retains the exact pending pointer bytes in recovery and marks the pointer
`superseded_by_restore`, including same-revision restores. Pending records remain retained separately and can be loaded explicitly for
review if stale; they cannot silently rebind locks or change acceptance. The state
pointer remains the sole owner of working and accepted revisions. No viewer-specific
processing engine or acceptance shortcut exists. UI RGB8/support8/alpha8 images are
viewing approximations, never replacements for authoritative precision layers.

## Optional assisted review history

Schema-1 manual processing requests remain compatible. Prepare/repair optionally accept `assisted_review` as defined by [the assisted workflow](assistant-workflow.md). Immutable `requests/review-<identity>/000-<content-sha256>.json`, `001-<content-sha256>.json`, etc. record the original explicit cycle request, reservations and source comparisons with content-addressed filenames and predecessor hashes. Terminal-byte changes, missing/reordered predecessors, contradictory transitions and lost reservations referenced by retained recovery requests fail closed. A per-cycle `head.sha256` integrity anchor binds the latest event, detecting removal of a valid terminal suffix as well as altered bytes. Events publish before the atomic anchor update; any partial event/anchor publication fails closed and remains retained for inspection. The anchor owns no working/accepted pointers or separate attempt counter. The single project lock serializes writes. This history is advisory, not another working/accepted state authority. A repair reservation is durable before model execution and reused by the same resume request. Two attempts total are shared across all defects; judgement is required between attempts. Stop keeps the best valid revision identity without changing acceptance or restoring drafts. Original prepare/repair requests/results and recovery snapshots retain existing meanings.

Current `review` exports include current working/accepted/draft identities, selected revision draft digest, frozen actual recipe/model settings, authoritative asset paths, structural QA, crop-image hashes and stale/effects labels. These fields are additive; existing RGB8/alpha8 panels, exact native crop origins/scales and full-precision layer contracts remain unchanged. A refreshed manifest receives a new content-addressed directory when current draft/state labels change. Saved revision-local before/after panels describe that operation's immutable comparison; obtain a current `review` export before proposing another correction. Cleanup availability and actual enabled/stale state are explicit; protected inward shading uses the additive contract below.


## Optional source-guided color cleanup

Schema-1 `effects` requests extend the finite `run` operation. Common identity fields
are unchanged. Require `scope_xyxy`, project-relative `support_file` (aligned scalar16),
and boolean `candidate_comparison`. Optional `color_cleanup` overrides the current recipe
section with enabled boolean and finite strength in [0,1]. A complete accepted base
or explicit candidate comparison is required to enable nonzero cleanup. Old requests
and projects remain valid; no migration or model setup is needed.

Complete effects revisions retain unchanged `base_alpha16.png` and base
`foreground_rgb16.tif`, plus separate profiled `corrected_rgb16.tif`, canonical
`effects/support16.png`, dependency `effects/alpha16.png`, immutable actual
`effects/settings.json` and the operation's `effects/write_support16.png`. The manifest
hashes every file and records actual strength, enabled/stale state, master identity,
alpha/support hashes, native scope, algorithm and parent manifest identity. The parent
chain retains prior scoped settings; latest strength describes the latest patch, not
an implicit global rewrite. Cumulative support/dependency maps describe retained layers;
each immutable effects revision retains its exact write support and settings.
Current review exports project `settings.color_cleanup` from the validated saved
manifest's applied enabled/strength values, including inherited effects and zero/off
semantics. Stale enabled cleanup retains those settings; `effects.color_cleanup.stale`,
`cleanup_stale` and the selected base asset identify its temporary exclusion from the
view. Other settings come from the consumed recipe snapshot. The saved `recipe.toml`
and `draft_digest` remain exact consumed draft inputs, including when an operation
overrode cleanup settings.

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


Effects revisions bind their `draft_digest`, saved recipe and saved guides to the
actual consumed snapshots. Recipe-only cleanup/notes edits can therefore be reviewed,
accepted and restored exactly. Changed guidance or mask-affecting recipe sections
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

Schema-1 `effects` retains its common identity, `scope_xyxy`, `support_file` and
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
application or second compositing mode is permitted. Off/p=0 is identity relative
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


## Optional local exposure

`local_exposure` is an optional schema-1 recipe section with exactly `enabled`
(boolean) and `ev` (finite number in [-3,3], excluding booleans). Missing means
OFF / 0 EV in memory. Reading legacy recipes does not rewrite their bytes or
immutable revision digests. New projects default to OFF / 0 EV.

An exposure-only schema-1 `effects` request uses the existing master/base/draft
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
`schema_version=1`, enabled/settings/stale, `source_id`, scope, candidate comparison,
`support_sha256`, `protection_sha256`, `alpha_sha256`, optional `area_sha256`
(null for scalar inputs), and algorithm `linear-srgb-local-exposure-v1`.
The settings asset equals the record. Dependency types, identities, hashes,
dimensions, categorical protection and authored geometry are validated even OFF.
Request, draft, source, parent, area and protection inputs are rechecked before
atomic publication under the canonical writer lock. Accepted state is unchanged.

Selection order is original saved foreground, optional saved cleanup, local
exposure, optional Shadow fade, existing encoded-sRGB shading, alpha composition. For eligible pixels,
decode sRGB to linear RGB, multiply by `2 ** (ev * support16 / 65535)`, clamp to
[0,1], encode to sRGB and quantize once with float64/ties-to-even RGB16.
The sRGB thresholds are .04045 (decode) and .0031308 (encode). Alpha does not
scale the exposure gain. Zero-alpha, zero-support and protected RGB are exact;
alpha never changes. OFF and 0 EV take exact identity paths. Exposure always
starts from the unexposed saved layers and cannot compound on repeated requests.
Saved RGB locks snapshot selected pre-shading RGB, including exposure and fade,
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

When exposure is present, exports retain selected `foreground_rgb16.tif`,
`unexposed_foreground_rgb16.tif`, `base_foreground_rgb16.tif`, source/alpha,
`exposure_support16.png`, `exposure_protection16.png`,
`exposure_alpha16.png`, `exposure_settings.json`, and authored
`exposure_area.json` where present. Shading W16/opacity remain independent.
The unexposed export remains cleanup-selected RGB before both exposure and fade.
Reconstruct by applying exposure once, then optional fade once, then the existing
shading/alpha renderer. The selected foreground already
contains exposure; applying it again would be incorrect. Reduced-precision
views remain explicitly labelled. Restore selects immutable saved inputs without
changing final acceptance; no model inference or download is involved.


## Optional Shadow fade

The optional schema-1 recipe section `shadow_fade` has exactly `enabled` (strict
boolean), `amount` and `preserve_highlights` (finite int/float, excluding booleans,
in [0,1]). Defaults are OFF / 0 / 1. Either this section or `local_exposure` may
be absent independently. Missing means OFF in memory; read/reopen never rewrites
legacy root or immutable recipe bytes. Existing revisions stay recoverable through
explicit restore. Older applications are not promised forward compatibility with
new effect records; preserve a separate pre-extension project for older binaries.
Never strip a new effect record to force an older reader to accept it.

A separate schema-1 `effects` operation uses the common identities,
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

Fade follows cleanup and local exposure, before encoded-sRGB shading and alpha.
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
The optional manifest `shadow_fade` record has exactly `schema_version=1`,
`enabled`, `settings`, `stale`, `source_id`,
`algorithm="linear-srgb-shadow-fade-v1"`, `scope_xyxy`, `candidate_comparison`,
`support_sha256`, `protection_sha256`, `alpha_sha256`, `area_sha256` (null for
scalar input). Settings JSON equals the record. Hashes, types, dimensions,
categorical protection, geometry equality and stale/dependency status validate
even OFF. Unbound area files reject before warm-cache return. Bounded semantic
caches retain no image arrays and never bypass current asset hashing.

Prepare retains operands; matte/repair recompute alpha staleness and union new RGB
locks into protection. RGB locks save the selected pre-shading appearance and
cannot receive fade twice. Changed upstream cleanup/exposure settings recompute
luminance from current unfaded RGB; there is no cached tonal mask to rebind.
Changed alpha makes enabled fade stale until explicit rebuild or disable.
Any stale enabled effect disables all optional effects in labelled BASE comparisons
and blocks final acceptance/export. Recover each stale effect independently.
Writes use the shared nonblocking project lock, staged complete revision and
state-last atomic pointer update, with snapshot rechecks before publication and
pointer replacement. Interrupted pointer replacement may retain a complete orphan;
only state is authoritative. Explicit restore/retry preserves accepted work.

`shadow_fade_off=true` in layer selection and `/image/.../shadow-fade-off` in
review retain cleanup, exposure and shading. Exposure-OFF retains fade and
recomputes its weighting from exposure-OFF RGB. BASE disables all optional effects.
The UI selects one comparison at a time. Comparison writes no revision.
Reset saves fade OFF / amount 0, retaining area, other effects and pending area edits.

Exports retain selected `foreground_rgb16.tif` (exposure and fade applied once),
`unfaded_foreground_rgb16.tif` (cleanup+exposure),
`unexposed_foreground_rgb16.tif` (cleanup before both exposure and fade),
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

Background-bearing revisions bind `background/background_rgb16.tif` and
`background/settings.json` in `files`. The optional manifest `background` has
exactly `schema_version:1`, `algorithm:"smooth-tonal-background-v1"`, `master_id`,
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
where F is selected RGB16 after cleanup/exposure/fade, A=alpha16/65535,
H=1-opacity*W16/65535 and B is the saved RGB16 backdrop. H applies only to F;
alpha applies once, with no earlier rounding. Black compatibility keeps the
existing arithmetic order. Protected underlying RGB/alpha remain exact while
partial-alpha flattened colour changes with B. Clipping diagnostics are independent.

Schema-1 `kind:effects` accepts exclusive `background` settings with all existing
master/base/draft/candidate identities and full native `scope_xyxy`. It cannot
combine foreground controls, area/support/protection inputs or amount-only flags.
It uses the canonical writer lock, snapshots, rechecks, immutable publication and
state-last pointer. An effective recipe is retained with the revision; its editable
copy is atomically updated before state publication. On interruption, accepted
state stays intact, the draft may differ, and a complete orphan can be explicitly
restored with draft replacement. Newer drafts are never silently overwritten.
Other operations inherit exact assets/settings and reject unapplied background
draft differences; alpha repair does not stale or rebuild B. Existing foreground
stale flags still block acceptance/export. Prepared revisions remain non-acceptable.

New background-bearing exports add `result_rgb16.tif`, `result_RGB8_VIEW.png`,
`background_rgb16.tif`, `background_settings.json`, a `background` record and
`result_compositing` description. Result uses B; existing black and transparent
files retain their meanings. Selected foreground is pre-shading and already
exposed/faded: do not replay these twice. Saved F/A/W/opacity/B reconstruct Result
without source, models, cache or analytic generation. All RGB16 TIFFs carry sRGB.
Legacy exports keep their old file set/metadata and identical-delivery reuse;
differing-content collisions are refused. Existing immutable legacy reviews are
not regenerated on open. Current readers restore prior revisions; old readers
are not promised to understand new records. Retain a prior project/revision for
recovery rather than stripping fields. No automatic cleanup occurs.

## Framed presentation exports

`export PROJECT --margins LEFT RIGHT TOP BOTTOM [--framed-transparent]` adds a
separate presentation delivery. Omitted margins retain the native export contract
and file set. Explicit zero margins still select a compact presentation.
Each margin is a nonnegative integer in native pixels. Output width/height must
each be at most 32768 and their product at most 100,000,000; requests are checked
before staging or expanded raster allocation. Native dimensions, editing
coordinates, saved layers, acceptance and project schema do not change.

The canonical saved renderer completes the native Result once, including selected
cleanup/exposure/fade, shading and alpha. Framing copies those RGB16 samples without
resampling at `(left, top)`. Outside that rectangle, only the saved native backdrop's
nearest edge/corner pixels extend outwards; legacy backdrop absence means black.
No foreground edge is stretched and no larger analytic backdrop is regenerated.
The optional straight RGBA8 view retains the canonical native viewing samples and
has zero RGB and alpha outside. All delivered rasters carry the canonical sRGB ICC
profile; TIFF is uncompressed processed RGB16, PNGs are reduced-precision views.

The flat directory `exports/<revision[-DRAFT]>-framed-<full-sha256>/` contains
`result_rgb16.tif`, `result_RGB8_VIEW.png`, optional
`transparent_RGBA8_VIEW.png`, `README.txt` and `manifest.json`.
The schema-1 manifest has kind `framed-presentation`, master/revision identities,
exact validated revision-manifest byte hash, source/output dimensions, margins,
half-open `source_rect_xyxy`, algorithm `saved-backdrop-edge-padding-v1`,
encoding/profile/variant identities, selected effect/backdrop identities and
project-relative native-asset hashes. Its `files` records hash every delivered
member except the manifest itself, with raster dimensions and precision.
The directory identity hashes the canonical manifest inputs before delivered-file
records are added. The bundle excludes capture paths, model configuration and
editable native rasters; keep the local project for further editing.

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
Failed stages and prior deliveries remain available.

Resource admission retains the 10 GiB disk reserve and adds the existing native
allowance plus 16 bytes per framed pixel and 2 MiB. Expanded variants/readbacks are
processed sequentially; RGB8 conversion uses one row of float64 scratch and PNG
readback hashes decoded rows. Admission is a disk-capacity estimate, not a RAM
estimate/reservation or a guarantee that every supported size fits current memory.


## Saved framing and bounded preview

Optional `framing.json` is an independent schema-1 source preset. It contains exactly
`schema_version: 1`, `master_id`, `source_dimensions_wh: [width, height]` and `margins`
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
`master_id`, `revision`, `revision_manifest_sha256` and `margins`. It requires a
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
