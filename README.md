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
accepted RGB16 black/alpha16 exports and labelled PNG8 viewing copies. Run matting
directly after preparation to review the actual masked photograph.

Scoped repairs save quantized operands for replay without models. Restore selects
saved working inputs without changing final acceptance. `status` and `resume`
recover verified tiles or completed stages from interrupted matte/repair operations.
The offline loopback review window provides typed guide authoring, native
comparisons and the same processing and recovery controls. Optional assisted
review records bounded, source-based judgements through those same operations.

The optional appearance effects start disabled. Source-guided color cleanup saves
RGB16 layers with scoped stale/rebuild controls. Protected inward shading keeps
W16 and opacity independent and supports exact editable exports. Local exposure
has its own offline brush/rectangle areas, protections, reversible EV adjustment
and exposure-only comparison. Shadow fade independently darkens soft subject areas
in linear light, with Amount, Preserve highlights, explicit protection and a
fade-only comparison.

Background appearance saves a tone and broad variation behind the matte. New
projects start warm near-black (`#120708`, variation 55%); older projects stay
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
PNG/MPO and multi-image JPEGs (including Ultra HDR gain maps) are rejected;
export one SDR JPEG/PNG8 or a trusted uncompressed sRGB RGB16 TIFF first.

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
The existing CLI `accept --development --master-id ID` remains an optional legacy
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

## Source map

| Area | Owner |
| --- | --- |
| Content detection, RAW development, orientation and RGB16 | `src/blackmask/ingest.py` |
| Validated DNG white-point/calibration fallback and recorded multipliers | `src/blackmask/dng_white_balance.py` |
| Identity, shared writer lock, publication and approval | `src/blackmask/project.py` |
| Preparation snapshots and selected candidate publication | `src/blackmask/operations.py` |
| Typed native guides and categorical rasterization | `src/blackmask/guidance.py` |
| Pinned explicit setup and local-only SAM/ViTMatte sessions | `src/blackmask/models.py` |
| Quantized scoped merge and saved operand replay | `src/blackmask/repair.py` |
| Native tile geometry, blending and verified cache | `src/blackmask/matte.py` |
| Same-native-crop review assets | `src/blackmask/review.py` |
| Canonical precision renderer and accepted/draft exports | `src/blackmask/export.py` |
| Source cleanup, protected inward W16 and independent effect publication | `src/blackmask/effects.py` |
| Independent native area and linear-sRGB local exposure | `src/blackmask/exposure.py` |
| Independent linear-sRGB Shadow fade and saved operands | `src/blackmask/shadow_fade.py` |
| Independent native RGB16 backdrop and saved settings | `src/blackmask/background.py` |
| Typed editable recipe/groups | `src/blackmask/recipe.py` |
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
output outside this repository or under the ignored root `local/` directory.
Ignored files are not disposable and are not backed up by Git. Arrange independent
backups. Common photo formats are ignored; only deliberately owned synthetic test
fixtures may be included beneath `tests/fixtures/`. Review actual staged content
before publishing: ignore rules do not remove existing history or prevent force-add.

The application history contains no photographs or frozen reference archives.
Reviewed development plans are retained in Git under `docs/incremental-plans/` and
`docs/superpowers/`, alongside the original
[v4 product specification](single-photo-black-background-implementation-plan-v4-2026-10-11.txt).
These records preserve requirements, decisions and evidence from their stated
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
