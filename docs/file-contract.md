# I01 photo project contract

One project contains one untouched source reference and one developed master.
`source.json` records original resolved path/SHA-256, detected format, original
precision (RAW captured precision unknown), original dimensions/profile hash where
available, applied orientation owner, crop/development decisions, output encoding,
clipping count and master file hash. The original remains outside writable assets.

`masters/<master_id>.tif` is uncompressed RGB16 with embedded canonical sRGB ICC.
Identity is SHA-256 of canonical JSON development/source metadata followed by
contiguous little-endian RGB16 samples. Dimensions alone never establish identity.
RAW orientation is applied by LibRaw; other EXIF transforms are applied once by the
ingest owner. Coordinates begin at the oriented master top-left. Future points use
integer pixel indices; boxes are half-open [x0,y0,x1,y1). No guides are active yet.

`recipe.toml` is typed schema 1 with identity, `guides_file="guides.json"`, editable
notes and empty groups. I01 requires the declared defaults: matting 1024/256/auto,
color cleanup disabled/strength .35 and shading disabled/opacity 0. Unknown keys,
malformed types or unavailable processing settings fail visibly. Future owning
increments extend validation with their implemented behavior. Prose is never code.
`guides.json` contains schema, identity, dimensions and empty regions.

`state.json` alone owns `working_revision`/`accepted_revision` (both null in I01),
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

RGB8 proxy creation, masks, revisions, final acceptance, effects and exports arrive
in later increments. Never use a flattened preview as a master. The complete
manual viewer and registration controls are not yet implemented.

Initial assets/state use atomic create-if-absent hard links within the project filesystem; concurrent externally created files cause a visible collision and remain unchanged. Own staged files may remain as diagnostic hard links and are never authoritative. Approval alone uses atomic replacement of existing state. RAW rejected coefficients use null for non-finite values, recorded shape and an explicit validity flag; finite values remain recorded.
