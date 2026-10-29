# Image Mask

A local workflow in development for turning one photograph into a black-background
image while preserving photographed detail. It combines editable masks, scoped
repairs and optional reversible color cleanup and inward shading. Photographic
quality takes priority over reducing recurring effort.

The intended workflow uses a native macOS/Apple Silicon Python engine, a small
localhost review window and optional Codex assistance. After explicit setup, the
complete manual workflow must remain usable without an assistant, credits or
internet access.

## Current status

The application creates and reopens trusted RGB16 projects without requiring
source-development approval. Masking preserves the saved source lighting and colours;
appearance changes require an explicit user request or manual control action.
Typed native-coordinate guides produce named SAM
candidates, selected membership groups and categorical trimap/support/protection
assets. Optional morphology proposals use native-pixel margins and require separate
review against the source. ViTMatte runs at native resolution, with optional trimap
confirmation and separate final-photo acceptance, matching native-crop review assets,
accepted full-size Result RGB16 TIFF exports and same-size PNG8 viewing copies. Run matting
directly after preparation to review the actual masked photograph.

New projects use storage schema 2 and developed-image identities. Immutable masks,
RGB16 layers and effect operands are shared within the project; revisions retain
text and a small overview. Old schema-1 projects are preserved and rejected without
migration. Effective revision recipes and consumed draft snapshots are separate.
Latest generated result history survives restore and acceptance changes.

An optional [configured photo library](docs/library.md) safely creates Inbox,
Photos, Results Preview and Comparisons. Explicit import moves a validated capture
and declared sidecars once into a stable named photo folder, with interruption
recovery and duplicate-source protection. Configured pinned model directories are
shared across photographs. Import creates no result or gallery image.
Complete native generation maintains one reduced JPEG per imported photo with a
Draft/Accepted footer and explicit pending recovery. It follows the latest generated
Result independently of restore/export; see the [gallery contract](docs/file-contract.md#current-result-gallery).
Repeating a fully validated equivalent effects Apply reuses the current result,
preserving pending drafts and acceptance; [reuse rules](docs/file-contract.md#unchanged-effects-results) describe conservative misses.

Explicit export includes the selected Result pair, recipe, manifest and notes.
Black and transparent alternatives are independent opt-ins. Complete editable
layers are optional: native exports include them in the same folder; presentation
exports add a native editable companion and retain
their selected geometry. An intact matching delivery is validated and reused
before rendering. See the [delivery contract](docs/file-contract.md#requested-result-deliveries).

Scoped repairs save quantized operands for replay without models. Restore selects
saved working inputs without changing final acceptance. `status` and `resume`
recover verified tiles or completed stages from interrupted matte/repair operations.
The offline loopback review window provides typed guide authoring, native
comparisons and the same processing and recovery controls. Optional assisted
review records bounded, source-based judgements through those same operations.
Explicit [focused comparison sheets](docs/file-contract.md#focused-comparisons) save
selected crops and optional presentation previews, with native evidence retained
only when requested.

The optional appearance effects start disabled. Source-guided color cleanup saves
RGB16 layers with scoped stale/rebuild controls. Protected inward shading keeps
W16 and opacity independent and supports exact editable exports. Local exposure
has its own offline brush/rectangle areas, protections, reversible EV adjustment
and exposure-only comparison. Shadow fade independently darkens soft subject areas
in linear light, with Amount, Preserve highlights, explicit protection and a
fade-only comparison.

**Local sharpening** enhances captured detail in authored areas, with Amount,
Detail size (0.5–8 native pixels), Noise guard, hard protection and an OFF comparison.
It runs after cleanup and before exposure; it never changes alpha or invents detail.
See [Local sharpening](docs/workflow.md#local-sharpening) for limits and recovery.

**Fade into background** blends subject colour toward the chosen background using
an editable oval, independently directed arcs, or both. It preserves alpha and
keeps Shadow fade independent. Local **fade reduction** brushes and rectangles can
reduce either effect independently without changing saved areas, protection or alpha. See the [offline walkthrough](docs/workflow.md#fade-into-background)
for shape controls, saved strength maps, recovery and portable two-folder exports.

**Appearance recipes** save selected scalar settings or an editable fade layout
from a complete saved revision as a portable JSON file, with an optional source-photo thumbnail. Open the file on
another photo, load chosen values into controls, then Apply each effect explicitly.
Widths adapt to the saved subject bounds; areas, protection, fade reduction and
master effect switches stay local. Layout imports have explicit Add/Replace and
Undo controls. See [reuse appearance settings](docs/workflow.md#reuse-appearance-settings)
for privacy, sequential Apply and stale-draft recovery.

**Background light** adds one independent Soft oval or Broad directional gradient
behind the saved matte. It starts OFF, preserves the foreground and keeps the
unlit base as the fade target. Native editable exports retain its separate field,
including OFF. See the [light and gentle exposure walkthrough](docs/workflow.md#background-light).

Background appearance saves a tone and broad variation behind the matte. New
projects start warm near-black (`#120708`, variation 55%); schema-2 recipes without background settings stay
black until explicitly changed. The [background instructions](docs/workflow.md#background-appearance)
explain Result, diagnostic views and separate editable exports. Presentation framing
adds saved margins, a separate bounded RGB8 layout preview and compact RGB16
exports. Native masks and editing coordinates stay unchanged; see
[presentation margins](docs/workflow.md#add-presentation-margins). **Match series**
fits the saved masked subject into fixed output dimensions, with portable JSON
presets for manual reuse across photographs. It resamples a separate presentation;
**Add margins** retains its exact native-copy behavior. See the
[series workflow](docs/workflow.md#match-a-fixed-size-series) and
[verification limits](docs/validation.md#fixed-size-series-framing).

[Validation](docs/validation.md#combined-workflow-validation) records combined
computational checks and reconstruction from saved assets alone. The representative
human pilot remains pending. Implementation delivery does not establish acceptance
for regular use.

A public Kodak RAW passed bounded native ingest/master round-trip checks. Pinned
SAM passed real CPU and separate MPS synthetic geometry checks; auto stays CPU.
User-selected RAW and human photographic evaluation remain pending. Synthetic
model output does not establish photographic quality.

## Setup and quick start

Use native ARM64 Python 3.12 on macOS. The project does not install Python or
download models implicitly. Reserve at least 10 GiB free **plus** estimated pending writes;
the doctor reports current disk/environment information. One environment is enough.
From the repository root, with your selected Python 3.12 executable:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install --require-hashes --only-binary=:all: -r requirements-macos-arm64.lock
.venv/bin/python -m pip install --no-build-isolation --no-deps -e .
.venv/bin/blackmask doctor
.venv/bin/blackmask open /path/to/capture.tif --project /path/to/new-photo-project --sam-cache /path/to/sam-cache --model-cache /path/to/vitmatte-cache
.venv/bin/blackmask open --project /path/to/new-photo-project --sam-cache /path/to/sam-cache --model-cache /path/to/vitmatte-cache
```

Choose three independent locations: the installed application environment (here
`.venv` with this source checkout), your photo project or optional
[configured library](docs/library.md), and your explicitly installed
[pinned models](docs/model-provenance.md). Replace every `/path/to/...` placeholder
with your selected path. No pre-existing `local/` directory, pilot project,
assistant history, personal reference or paid service is required. Model setup is
separate from the package install; retain those assets for offline processing.
Use the absolute path to the environment's `bin/blackmask` when working from
another directory; the relative `.venv/bin/blackmask` examples assume the checkout
root. Keep an editable installation's source checkout in place; recreate its
environment from the lock if changing its location rather than copying a venv.
Optional [browser verification](docs/validation.md#reusable-isolated-browser-setup)
and [named references](docs/assistant-workflow.md#named-local-references) use
separately selected locations and are not needed for ordinary manual editing.

`open` starts one foreground server bound to `127.0.0.1` on an available port and
opens the packaged review page in your browser. Keep that terminal open; Ctrl-C
stops the server without discarding saved work. Reuse its printed launch URL if
browser opening fails. The URL grants access to this project: keep it local.
`--headless` creates/validates and returns JSON for automation without starting a
server. Model cache arguments select existing explicitly installed assets; they
never download. Preparation can also use `BLACKMASK_SAM_CACHE`, and matting
`BLACKMASK_VITMATTE_CACHE`. See [the complete manual workflow](docs/workflow.md)
for new guide/support/lock authoring, separate approvals and recovery, including
the [numbered offline use check](docs/workflow.md#numbered-offline-use-check).

The project location must be new/empty, separate from the capture and free of
symlink aliases. Source paths are detected by content, never by extension. For
missing RGB profiles, explicitly add `--assume-srgb` only if that assumption is
correct. TIFF input is single-page, uncompressed, contiguous RGB16 sRGB; currently
recognized high-depth ICC profiles match LittleCMS's canonical sRGB transform
bytes with header creation time/profile ID ignored. Other high-depth profiles
require a trusted sRGB TIFF export; this is a deliberately conservative limit.
Opaque RGB JPEG/PNG8 profiles are converted through LittleCMS when necessary;
8-bit captures gain no precision by entering the 16-bit container. Alpha-bearing
images, compressed TIFF, RGB16 PNG and non-RGB input are rejected. Multi-frame
PNG/MPO and multi-image JPEGs are rejected by default. For a supported SDR-base
gain-map JPEG, explicitly add `--jpeg-sdr-primary` to `open` or `import` to use
only its ordinary SDR image. The complete original stays intact; HDR brightness
is omitted. Other multi-image files remain unsupported. See the
[SDR-primary import contract](docs/file-contract.md#explicit-sdr-primary-jpeg-import),
or export one SDR JPEG/PNG8 or a trusted uncompressed sRGB RGB16 TIFF first.

RAW/DNG uses LibRaw, full-size AHD and explicit sRGB gamma/WB/brightness settings.
LibRaw identifies TIFF-container RAW before ordinary TIFF import; an RGB8 preview
in its first page never becomes the working master. Recognized RAW failures stop
rather than falling back to that preview.
When the reader cannot expose camera white-balance multipliers, supported RGB DNGs
use their recorded `AsShotWhiteXY` and calibration profiles, including the Pixel 8's
capture-specific third calibration. The applied multipliers and provenance are
saved with the master. Unsupported or unusable as-shot metadata still requires an
explicit `--white-balance daylight` preview or an already-developed trusted TIFF;
the tool never silently substitutes daylight. See the [saved white-balance contract](docs/file-contract.md#raw-as-shot-white-balance).
There is no general RAW editor or crop control.
The local page shows a labelled RGB8 source preview. Mask preparation can start
immediately; there is no source-development approval gate. To retain lighting and
colour edits made in another application, import a supported developed image,
preferably trusted uncompressed RGB16 sRGB TIFF. RAW decoding still applies the
recorded conversion above; it is not a replacement for that application's rendering.
Masking adds no exposure, white-balance or colour correction to the saved master.
The existing CLI `accept --development --developed-id ID` remains an optional legacy
review record for compatible scripts; it is never a prerequisite or final-photo acceptance.

Changing development currently requires a separate project/master identity; dimensions
alone cannot preserve later guides. Reopen uses saved validated assets and works
without the original path being available; preserve the original separately.
Do not substitute a same-name capture if its recorded hash differs.

```sh
.venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check src tests --no-cache
.venv/bin/ruff format --check src tests --no-cache
.venv/bin/mypy src
```

See [bounded assisted review](docs/assistant-workflow.md), [native matting and exports](docs/matting.md), [file contract](docs/file-contract.md), [validation and limitations](docs/validation.md),
[recovery](docs/troubleshooting.md) and [exact package/development provenance](docs/model-provenance.md).
Setup requires public package downloads; subsequent processing is local/offline. See [selection and guides](docs/guidance.md)
for explicit model setup, typed preparation and human review.

The repository-local [`photo-directions` skill](.agents/skills/photo-directions/SKILL.md)
offers read-only advice for a selected photo and intention, using current controls.
See the [invocation and capability table](docs/assistant-workflow.md#photo-directions)
for Codex, OpenCode 2 and Antigravity, including pending native-host validation.
Extra ideas and watermarked AI concepts are independent options; concepts require
suitable built-in host tools and may not be reproducible with current controls.
The skill applies no photo edits.

## Source map

| Area | Owner |
| --- | --- |
| Content detection, RAW development, orientation and RGB16 | `src/blackmask/ingest.py` |
| Validated DNG white-point/calibration fallback and recorded multipliers | `src/blackmask/dng_white_balance.py` |
| Identity, shared writer lock, publication and approval | `src/blackmask/project.py` |
| Explicit library configuration, original ownership and import recovery | `src/blackmask/library.py` |
| Latest native Result gallery, footer and derivative recovery | `src/blackmask/previews.py` |
| Preparation snapshots and selected candidate publication | `src/blackmask/operations.py` |
| Typed native guides and categorical rasterization | `src/blackmask/guidance.py` |
| Pinned explicit setup and local-only SAM/ViTMatte sessions | `src/blackmask/models.py` |
| Quantized scoped merge and saved operand replay | `src/blackmask/repair.py` |
| Native tile geometry, blending and verified cache | `src/blackmask/matte.py` |
| Read-only cache inventory and exact confirmed clearing | `src/blackmask/operations.py`; [cache contract](docs/file-contract.md#inspecting-and-clearing-processing-cache) |
| Native review evidence and explicit focused comparison sheets | `src/blackmask/review.py` |
| Canonical precision renderer and accepted/draft exports | `src/blackmask/export.py` |
| Source cleanup, protected inward W16 and independent effect publication | `src/blackmask/effects.py` |
| Alpha-aware linear-luminance local sharpening and saved operands | `src/blackmask/sharpening.py` |
| Independent native area and linear-sRGB local exposure | `src/blackmask/exposure.py` |
| Independent linear-sRGB Shadow fade and saved operands | `src/blackmask/shadow_fade.py` |
| Native oval/arc fields and background-targeted colour blend | `src/blackmask/spatial_fade.py` |
| Bounded, editable local fade reduction geometry | `src/blackmask/fade_reduction.py` |
| Independent native RGB16 backdrop and saved settings | `src/blackmask/background.py` |
| Independent backdrop light field, bindings and B0/B1 composition | `src/blackmask/background_light.py` |
| Shared immutable raster references and role validation | `src/blackmask/assets.py` |
| Typed editable recipe/groups | `src/blackmask/recipe.py` |
| Portable appearance recipes and subject-relative scalar/layout conversion | `src/blackmask/appearance_recipes.py` |
| Presentation geometry, bounded sampling and source-bound preset | `src/blackmask/framing.py` |
| Fixed-size subject layout, premultiplied resampling and portable series settings | `src/blackmask/series_framing.py` |
| One-project loopback server and packaged manual page | `src/blackmask/viewer.py`, `src/blackmask/ui/review.html` |
| Shared inverse native coordinate mapping | `src/blackmask/ui/coordinates.js` |
| Supported commands and local doctor/setup | `src/blackmask/cli.py` |
| Ingest, guide/model geometry, transactions and CLI regressions | `tests/` |
| Saved files and recovery | [File contract](docs/file-contract.md), [troubleshooting](docs/troubleshooting.md) |
| Observed checks and limits | [Validation](docs/validation.md) |
| Dependency/development settings and licences | [Provenance](docs/model-provenance.md), [third-party notices](THIRD_PARTY_NOTICES.md) |
| Contributor safeguards | [Repository guidance](AGENTS.md) |

## Local data and repository hygiene

Keep private captures, working projects, model assets, credentials and evaluation
output outside this repository, under the ignored root `local/` directory, or in an
explicitly configured ignored [photo library](docs/library.md).
Private named references may also live in root-level `references/`, with a catalog
at `references/README.md` and one self-contained folder per reference. Its contents
are ignored except for the empty `.gitkeep` placeholder and excluded from packages.
Supply the catalog path explicitly; see the
[reference and recipe workflow](docs/assistant-workflow.md#named-local-references).
Ignored files are not disposable and are not backed up by Git. Arrange independent
backups. Common photo formats are ignored; only deliberately owned synthetic test
fixtures may be included beneath `tests/fixtures/`. Review actual staged content
before publishing: ignore rules do not remove existing history or prevent force-add.

The application history contains no photographs or frozen reference archives.
Pending plans, QA obligations and their supporting records remain under
`docs/incremental-plans/` and `docs/superpowers/`, alongside the original
[v4 product specification](single-photo-black-background-implementation-plan-v4-2026-10-11.txt).
Retired implementation plans remain recoverable from Git history. These records
preserve requirements, decisions and evidence from their stated
baselines. Historical checkout paths, test counts and approvals describe those
baselines; they do not establish the state or authority for new work. Private
reference material and local evaluation evidence stay ignored. Development plans
are excluded from installable distributions and are not needed to operate the tool.

The [fixed-size series design](docs/superpowers/specs/2026-10-20-series-framing-design.md),
[design review](docs/superpowers/plans/2026-10-20-series-framing-review.md) and
[implementation plan](docs/superpowers/plans/2026-10-21-series-framing.md) retain
development decisions and evidence. The maintained workflow and file contract own
the supported interface; development records do not supply photographic acceptance.

The maintained user docs describe implemented behavior. Cleanup and shading
require human comparison for each photograph; synthetic checks do not supply
photographic acceptance.

## Licensing

No licence for original project code has been selected. Dependencies retain their
own terms; see [third-party notices](THIRD_PARTY_NOTICES.md) and [package provenance](docs/model-provenance.md).
No photographs or model weights are distributed. A checkpoint licence does not
license separate research code or grant rights to photographs.
