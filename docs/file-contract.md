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
notes and named groups. I02 keeps matting geometry at 1024/256, permits auto/cpu/mps,
color cleanup disabled/strength .35 and shading disabled/opacity 0. Unknown keys,
malformed types or unavailable processing settings fail visibly. Future owning
increments extend validation with their implemented behavior. Prose is never code.
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

I02 creates labelled RGB8 proxies and immutable prepared revisions. Native alpha,
final acceptance, effects and exports arrive in later increments. Never use a flattened preview as a master. The complete
manual viewer and registration controls are not yet implemented.

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
atomically advances working_revision. Accepted_revision remains null in I02.
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
never inference cache or accepted dependencies. No resume/restore/automatic
cleanup is implemented yet. Later writers must reuse these transaction and
identity owners and extend state validation when final acceptance arrives.
