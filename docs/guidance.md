# Selection and typed guides

Preparation produces guidance for review. It neither computes alpha nor accepts
a final photograph. After [environment setup](../README.md#setup-and-quick-start),
run commands from the repository root; shell activation is unnecessary. First
inspect the developed RGB16 master, then explicitly approve that master's actual
identity with
`.venv/bin/blackmask accept /path/to/project --development --master-id ACTUAL_INSPECTED_MASTER_ID`.

## Model setup and devices

One native ARM64 Python 3.12 environment and one cache are sufficient. The pinned
Torch wheels require macOS 14 or newer. Install the complete hash-locked package
set as in README. Download the public SAM assets only through an explicit setup:

```sh
.venv/bin/blackmask setup-model --model-cache /path/to/model-cache/sam2
.venv/bin/blackmask doctor --model-cache /path/to/model-cache/sam2
```

Setup verifies the exact [model/config hashes](model-provenance.md), reserves
10 GiB plus pending writes, and preserves existing files on mismatch. Model
loading uses explicit Sam2Model, Sam2Processor and Sam2ImageProcessorFast,
safetensors and local-only loading. Missing/corrupt assets fail without downloads.
No research framework, API key or paid service is used. Keep the cache outside Git.

`matting.device` controls selection too: `auto` currently selects CPU float32.
Explicit `mps` is diagnostic and fails visibly on unsupported operations, OOM or
non-finite output. Disable `PYTORCH_ENABLE_MPS_FALLBACK` to keep device failures
visible. Automatic MPS remains disabled pending representative photographic and
responsiveness checks. Its implemented failed-stage policy retries once on CPU
with unchanged geometry, without mixing embeddings/devices or reducing resolution.
Native ViTMatte matting has [separate explicit setup](matting.md#explicit-model-setup)
and [photographic review obligations](matting.md#recovery-and-limits).
Scores are model rankings, not calibrated quality probabilities.

## Recipe groups and native regions

Keep the created recipe's identity/default sections. `groups` accepts entries:

```toml
[[groups]]
id = "wing"
keep = true
material_policy = "unknown_interior"
# Add selected_candidate = 0, 1 or 2 only after inspecting returned candidates.
```

The policies are `unknown_interior` and `opaque_core`. Neither membership nor
material policy alone forces pixels to be opaque. Preparation starts entirely
unknown and uses explicitly confirmed native cores. Optional morphology produces
a separate, unreviewed suggestion, described below. It does not fill holes or
automatically certify background.

Guides schema 1 contains `master_id`, native integer `width`/`height`, and `regions`.
Each region needs a stable `id`, `role`, `shape` and its shape-specific fields.
IDs contain 1–64 ASCII letters/digits/underscores/hyphens, starting alphanumeric.
Points are integer pixel indices from the oriented top left. Boxes/rectangles are
half-open `[x0,y0,x1,y1)`, bounded by native master dimensions. A model/preview
coordinate must be mapped to native space before saving; equal dimensions do not
establish registration with a changed master.

| Role | Shapes and additional fields | Meaning |
| --- | --- | --- |
| `keep`, `remove` | `point` with `xy` and `group_id`; keep also permits `box` with `xyxy` | Positive/negative SAM membership hints; one keep box per group |
| `foreground` | `point`, `rectangle` (`xyxy`), `stroke` | Explicit confirmed opaque core, categorical 255 |
| `background` | same | Explicit confirmed empty background, categorical 0 |
| `unknown` | same | Search/uncertainty corridor, categorical 128; never draws strands |
| `support` | same plus `feather_px` | Full-master grayscale16 allowed-write support, clipped to request scope |
| `lock` | same plus `revision` | Protection bound to saved same-master alpha/RGB values |

A point paints one native pixel. A stroke has native `points` and positive integer
`radius_px`; it paints the union of circular-ended segments without antialiasing.
Support `feather_px=0` is valid. Positive feather uses distance inward from the
scope-clipped region boundary; distance/feather is capped at one and rounded once
to uint16. Hard locks and known/unknown labels stay categorical. Multiple support
regions combine by maximum, never add beyond full strength.

FG/BG overlap is rejected before inference even if an unknown corridor overlaps
it. Unknown overrides an otherwise single known label. Known assertions that
contradict saved lock values are rejected. For a saved parent alpha, a known core
needing change requires support exactly 65535; feathered/out-of-scope support is
not silently widened. Negative SAM hints do not certify background. Kept fragile
or translucent objects remain unknown except explicit source-verified solid cores.

Locks require an existing same-master revision containing alpha16. Preparation cannot
create initial alpha, so new projects cannot invent saved-value locks. Locks
persist until an explicit recorded remove action. Changing/shrinking/rebinding a
lock requires removal in one operation before a later upsert. Acceptance will not
create blanket locks. Preparation carries parent alpha/corrected RGB unchanged.

## Prepare and review

`.venv/bin/blackmask open --headless --project /path/to/project` returns current master, working revision
and draft `inputs_digest`. Copy those actual identities into a request, with null
base before the first revision:

```json
{
  "schema_version": 1,
  "kind": "prepare",
  "base_revision": null,
  "master_id": "ACTUAL_MASTER_ID",
  "inputs_digest": "ACTUAL_DRAFT_DIGEST",
  "guide_edits_file": "requests/guides-edit.json"
}
```

The optional edit file uses the same master and typed actions:

```json
{
  "schema_version": 1,
  "master_id": "ACTUAL_MASTER_ID",
  "actions": [
    {"action":"upsert", "region":{"id":"wing-hint","role":"keep","shape":"point","xy":[40,30],"group_id":"wing"}},
    {"action":"upsert", "region":{"id":"uncertain-edge","role":"unknown","shape":"stroke","points":[[20,10],[70,50]],"radius_px":3}}
  ]
}
```

Coordinates above illustrate schema only; choose source-supported coordinates
inside your actual master. Removal is `{"action":"remove","id":"ACTUAL_ID"}`.
One action per ID per operation prevents ambiguous precedence. Empty/malformed
regions, unknown keys, unsupported kinds and prose-as-code are rejected.
Optional request `scope_xyxy` bounds support; omission explicitly means full master
for preparation. `reason` is inert text. No effect or repair settings are executed.

```sh
.venv/bin/blackmask run /path/to/project --request /path/to/prepare.json --model-cache /path/to/model-cache/sam2
```

Use `BLACKMASK_SAM_CACHE` instead of the flag if desired. No model/cache is needed
when no membership hints exist. Returned candidates are named `group-ID-0/1/2`,
with native binary masks and model metadata. Inspect them against the source;
select an ordinal in the group recipe and prepare again using fresh identities.
Selected membership is saved separately from the trimap. Session embeddings are
bounded to one image/master/backend and reused across prompt updates in that
session; separate CLI calls reload rather than promise a persistent inference
cache. Missing key dependencies miss cache. Saved revision assets remain durable.

Inspect the returned categorical trimap, source proxy and support/protection overlays
in the [local review window](workflow.md), or inspect the saved paths in an external viewer. All-unknown is an
honest fallback, not an automatic quality result. Preserve source-visible fine
features by unknown corridors; never paint invented foreground. Human trimap
review is still required before native matting. `accept --revision` rejects every prepared
revision, including one carrying parent alpha. See [recovery](troubleshooting.md).


## Optional native morphology proposal

A kept group with an inspected `selected_candidate` may explicitly request:

```toml
[groups.morphology]
foreground_erosion_px = 12
unknown_dilation_px = 25
```

Place this subtable immediately after its `[[groups]]` entry. Both margins are
required nonnegative native-pixel integers, bounded by the master size. They are
saved with the exact group/candidate identity in the revision recipe and manifest.
Omitting morphology preserves existing trusted-master and preparation draft
behavior and all-unknown fallback; merely selecting membership does not force known opacity.

For `opaque_core`, Euclidean distance to background/image exterior greater than
the erosion margin suggests a conservative interior. Distance to the selected
mask at most the dilation margin defines its expanded search region; the remainder
around the core is an unknown boundary. Zero margins are valid. Holes are never
filled as foreground. `unknown_interior` suggests no opaque interior; its selected
mask/search region stays unknown except separately verified typed solid cores.
Selected fragile groups also protect overlapping proposals from other groups.
Derived uncertainty preserves explicit typed FG/BG; explicit unknown corridors
still override suggested cores. FG/BG, saved-value lock and change-required
core/full-support contradictions reject through the same rasterizer. No support
is widened or lock removed. No complement or negative hint certifies background.

Preparation returns `trimap_proposal_file` and `proposal_boundary_file`, alongside
the unchanged authoritative `trimap_file`. The categorical proposal is explicitly
`unreviewed` and saved separately as `trimap_proposal.png`; its binary native
morphological search band is `proposal_boundary.png`. Inspect it against the source
before supplying source-verified foreground/background cores through typed guide
edits. The proposal itself is never used as authoritative known values, alpha or
human trimap approval. Later matting must consume the confirmed trimap and retain
its human review control. A requested empty/over-eroded candidate can honestly
produce no suggested core; absent defensible source confirmation, unknown remains.
