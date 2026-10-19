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

The tool creates/reopens trusted RGB16 projects with explicit human development approval.
Preparation saves named SAM candidates, selected membership groups and categorical
trimap/support/protection assets through typed native-coordinate guides, plus
opt-in native-margin morphology proposals for separate source review. Native
ViTMatte processing provides separate trimap/final acceptance controls, native
same-crop review assets and accepted RGB16 black/alpha16 plus labelled PNG8 exports.
Scoped native repair now saves quantized operands for model-free replay; restore
selects saved working inputs without changing final acceptance. Interrupted matte/repair now resumes verified tiles or completed stages through
`status` and `resume`. An offline loopback review window provides typed guide
authoring, native comparisons and the same processing/recovery controls. Appearance
effects remain future work.
Prepared revisions require explicit human trimap review before matting.

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
Invalid camera WB requires an explicit `--white-balance daylight` preview or an
already-developed trusted TIFF. There is no general RAW editor or crop control.
The local page shows a labelled RGB8 source preview. Inspect the saved master TIFF in a trusted full-precision external viewer for
orientation, WB and clipping. For CLI approval, obtain JSON identities in a second
terminal with `.venv/bin/blackmask open --headless --project /path/to/new-photo-project`.
Copy that `master_id` only after your human review; this records development
approval, leaving final-photo acceptance empty:

```sh
.venv/bin/blackmask accept /path/to/new-photo-project --development --master-id ACTUAL_INSPECTED_MASTER_ID
```

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

See [native matting and exports](docs/matting.md), [file contract](docs/file-contract.md), [validation and limitations](docs/validation.md),
[recovery](docs/troubleshooting.md) and [exact package/development provenance](docs/model-provenance.md).
Setup requires public package downloads; subsequent processing is local/offline. See [selection and guides](docs/guidance.md)
for explicit model setup, typed preparation and human review.

## Source map

| Area | Owner |
| --- | --- |
| Content detection, RAW development, orientation and RGB16 | `src/blackmask/ingest.py` |
| Identity, shared writer lock, publication and approval | `src/blackmask/project.py` |
| Preparation snapshots and selected candidate publication | `src/blackmask/operations.py` |
| Typed native guides and categorical rasterization | `src/blackmask/guidance.py` |
| Pinned explicit setup and local-only SAM/ViTMatte sessions | `src/blackmask/models.py` |
| Quantized scoped merge and saved operand replay | `src/blackmask/repair.py` |
| Native tile geometry, blending and verified cache | `src/blackmask/matte.py` |
| Same-native-crop review assets | `src/blackmask/review.py` |
| Canonical precision renderer and accepted/draft exports | `src/blackmask/export.py` |
| Typed editable recipe/groups | `src/blackmask/recipe.py` |
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

The public implementation history contains no photographs, private planning or
reference archives. Local planning and frozen reference material, when supplied
separately, stay ignored and are not required to install or operate the tool.
The maintained public docs describe the behavior currently implemented. Future
appearance features require separate implementation and human photographic validation.

## Licensing

No licence for original project code has been selected. Dependencies retain their
own terms; see [third-party notices](THIRD_PARTY_NOTICES.md) and [package provenance](docs/model-provenance.md).
No photographs or model weights are distributed. A checkpoint licence does not
license separate research code or grant rights to photographs.
