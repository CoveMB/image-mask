# Native mask, review and base export

After development approval and [typed preparation](guidance.md), inspect the
source and authoritative prepared `trimap.png`. Values mean confirmed empty
background (0), unknown (128), confirmed opaque foreground (255). Candidate
membership and `trimap_proposal.png` are separate suggestions. Review the proposal
against source; express verified cores/corridors through typed guide edits and
prepare again. There is no automatic proposal promotion. An all-unknown trimap is
allowed when no defensible cores exist, without a quality guarantee.

Copy actual revision/master/digest from the returned preparation, then explicitly
confirm that exact authoritative trimap:

```sh
.venv/bin/blackmask accept /path/to/project --trimap --revision ACTUAL_PREPARED_REVISION --master-id ACTUAL_MASTER_ID --inputs-digest ACTUAL_DRAFT_DIGEST
```

Development, trimap confirmation and final-photo acceptance are distinct controls.
Only the human can supply photographic acceptance. Editing drafts or replacing
saved assets invalidates the confirmation. Confirming a proposal's filename does
not force its values into the authoritative trimap.

## Explicit model setup

One environment and model root suffice. Setup is the only network path. Use the
pinned model and configs; do not download research frameworks or substitute files.

```sh
.venv/bin/blackmask setup-model --model vitmatte --model-cache local/models/vitmatte
.venv/bin/blackmask doctor --model vitmatte --model-cache local/models/vitmatte
```

After setup, loading is local-only, explicit classes, safetensors and session hash
verification. CPU float32 is the baseline. `matting.device` supports `auto`, `cpu`
and diagnostic `mps`; auto currently selects CPU. Explicit MPS failures remain
visible. If auto MPS is enabled after later acceptance, its failed stage gets one
whole-stage CPU retry at identical geometry, with a separate backend cache key.
No fresh matte combines predictions across devices. Implicit PyTorch MPS fallback
must stay disabled.

Create a JSON request with the actual returned current values:

```json
{
  "schema_version": 1,
  "kind": "matte",
  "base_revision": "ACTUAL_PREPARED_REVISION",
  "master_id": "ACTUAL_MASTER_ID",
  "inputs_digest": "ACTUAL_DRAFT_DIGEST"
}
```

```sh
.venv/bin/blackmask run /path/to/project --request /path/to/project/matte-request.json --model-cache local/models/vitmatte
```

No guide edits repeat in the matte request. Prepare changed guides first and
confirm their new trimap. The separate model view is RGB8; native matting uses
1024-pixel tiles, stride 768/nominal overlap 256 and appended final origins. The
pinned processor pads only bottom/right to a multiple of 32; output padding is
removed. It never resizes this stage. Known-only tiles bypass inference. Finite
predictions are clamped, blended with positive sine-squared weights, valid known
cores enforced and alpha quantized once to scalar16. Saved partial-alpha and
applicable RGB locks survive every full rerun exactly. Unlocked foreground starts
from the approved RGB16 master. Acceptance itself is not a blanket region lock.

## Review and final-photo acceptance

The returned matte revision contains saved `base_alpha16.png`,
`foreground_rgb16.tif`, structural `qa.json` and `review/manifest.json`. Review
assets are native RGB8/alpha8 approximations; the contact sheet's panel order is
source, black, gray, white, alpha. Inspect the full-precision assets separately.
Human visual status remains pending until explicit final acceptance; computation
and synthetic fixture tests do not approve a photograph.

```sh
.venv/bin/blackmask review /path/to/project --revision ACTUAL_MATTE_REVISION
.venv/bin/blackmask review /path/to/project --revision ACTUAL_MATTE_REVISION --crops /path/to/native-crops.json
```

The crops file is a JSON list such as `[[10,20,110,120]]`, with half-open native
rectangles within this master. Every panel uses exactly that crop, without resize;
manifest records native origin, displayed dimensions and scale 1. New review
exports live separately under `reviews/`, leaving saved revisions immutable.
Inspect opaque/background cores, mixed wings/web, source detail and seams on
black/gray/white. After human photographic review of the current result:

```sh
.venv/bin/blackmask accept /path/to/project --revision ACTUAL_MATTE_REVISION
.venv/bin/blackmask export /path/to/project
```

Final acceptance requires current complete matte assets and unchanged master,
development and draft identities; a preparation alone is never acceptable.
Default export selects the retained accepted revision even when a newer candidate
is working. Explicit unaccepted exports require both flags:

```sh
.venv/bin/blackmask export /path/to/project --revision ACTUAL_MATTE_REVISION --draft
```

`exports/rev-NNN/` (or visibly labelled `rev-NNN-DRAFT/`) contains uncompressed
sRGB RGB16 black TIFF, scalar alpha16 lossless PNG and RGB8/RGBA8 viewing PNGs.
The single renderer computes `round(F * (alpha16/65535))` in float64, encoded
sRGB, ties-to-even, applying alpha once. Transparent viewing RGB stays straight,
never alpha-multiplied. No effects are enabled. Masks receive no ICC/gamma
transform. Existing identical deliveries can be reused; differing/incomplete
ones fail without overwrite. Retain saved foreground/master and alpha for editable
handoff; the flattened black image never becomes foreground.

## Recovery and limits

All operations use the same nonblocking writer lock and identity/snapshot checks.
A complete staged revision publishes exclusively, then state advances atomically;
acceptance changes only through its explicit control. Low disk, interruption,
non-finite predictions, stale edits or corruption leave accepted files/pointer
intact before publication. Reopen actual state after errors, especially directory
sync errors after pointer replacement. Temporary files and complete orphans are
not authoritative. Verified tiles may be reused on a fresh request; there is no
resume support for preparation. See [recovery](troubleshooting.md) for
matte/repair resume and saved revision restore. Cache is never the sole accepted copy.

Reserve 10 GiB plus conservative pending writes. Actual two-tile native synthetic
CPU inference peaked near 7.86 GB RSS on the tested host; this is an observation,
not a memory bound for every photo. Retain independent backups. Source-required
spider/dragonfly native photographic comparisons, private RAW development review,
final acceptance and regular-use evaluation remain human obligations.


## Scoped repair and exact replay

First identify a source-visible defect and explicitly choose its native context
and allowed write scope. Context can exceed the support; the tool cannot decide
photographic improvement for you. Create typed support/core/lock guide edits with
the existing preparation route, run `prepare`, inspect the returned assets and
explicitly approve that prepared trimap. Preparation preserves parental alpha and
foreground RGB and remains ineligible for final acceptance.

Copy the actual returned revision, master, digest and `support_file` into a repair
request. Both the exact returned absolute support path and its project-relative
form are supported. Other assets and aliases are rejected. Do not include
`guide_edits_file` again. A schema-1 request has the common identity fields plus:

```json
{
  "schema_version": 1,
  "kind": "repair",
  "base_revision": "ACTUAL_PREPARED_REVISION",
  "master_id": "ACTUAL_MASTER_ID",
  "inputs_digest": "ACTUAL_RETURNED_DIGEST",
  "context_xyxy": [7, 5, 76, 46],
  "scope_xyxy": [10, 10, 60, 35],
  "support_file": "ACTUAL_RETURNED_SUPPORT_FILE",
  "merge_policy": "replace",
  "reason": "Describe the source-visible defect and requested bounded correction"
}
```

These rectangles illustrate native half-open coordinates; choose your own from
the actual source. Support must be nonempty, full-master grayscale16 and zero
outside both rectangles. A known core requiring a change needs full-strength
support, and its requested change must be compatible with the merge policy.
Contradictions fail before inference. Existing persistent locks apply throughout;
outside support and inside locks, partial alpha and applicable foreground RGB
are preserved exactly. Inconsistent outside-scope lock bindings are rejected.

```sh
.venv/bin/blackmask run /path/to/project --request /path/to/project/repair.json --model-cache /path/to/installed-vitmatte
.venv/bin/blackmask review /path/to/project --revision ACTUAL_REPAIR_REVISION
.venv/bin/blackmask replay /path/to/project --revision ACTUAL_REPAIR_REVISION
```

The returned review manifest and saved `review-before/manifest.json` use the same
native context for source, before, after and alpha viewing panels. The default
`review` command retains those saved crops; `--crops` explicitly overrides them. Inspect saved
RGB16/alpha16 separately for precision; the panels are labelled RGB8 viewing
approximations. Final acceptance remains a separate human action using `accept
--revision`, and the existing accepted export stays available during repair.

Repair saves and reloads parent P, candidate C and support16 before merging.
Replace uses D=C; increase-only uses max(P,C); decrease-only uses min(P,C).
Directional requests need an explicit rationale in `reason`. With
w=support16/65535, the single arithmetic owner computes
`rint(P*(1-w)+D*w)` in float64 with ties-to-even, then copies saved locks exactly.
P=1000, C=3000, support=21845 gives 1667. The replay command validates immutable
hashes, parent bindings, crop mapping, order and exact published pixels without
loading either model or reading inference cache. Preserve saved operands and
their revision dependencies; cache is never their only copy.

## Restore working inputs

```sh
.venv/bin/blackmask restore /path/to/project --revision ACTUAL_SAVED_REVISION
```

Restore selects that revision's exact effective recipe/guides and working head under the
shared writer lock. It never assigns `accepted_revision`. Unsaved draft text is
rejected by default. To deliberately replace it, add `--replace-drafts`; all
previous draft/state bytes are retained in the returned recovery directory,
including malformed TOML/JSON. Immutable master/source/state/revision checks remain
strict; only current mutable draft parsing is deferred for this explicit recovery.
Draft files are atomic individually, followed by the working pointer. An
interruption between those writes can leave partial working drafts; the recovery
record retains their original bytes. Reopen and inspect before retrying. This
is recovery preservation, not resumability or a multi-file atomic transaction.
