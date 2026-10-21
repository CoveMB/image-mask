# Photo library storage design

Status: proposed design for implementation planning; no application changes authorized by this document. Date: 2026-10-19, America/Toronto.

## Purpose and authority

Organize repeated local single-photo work so originals remain intact, all settings and edit operands remain recoverable, results are easy to browse, and unchanged assets are not repeatedly stored. The user requested a Superpowers plan, evaluation against current code, and two separate fresh independent plan reviews with different focuses. That direct request supersedes the ordinary one-final-review limit for this planning task only. No implementation, publication, model download, photo processing, or deletion is included in this task.

The user says the project has no production users and backward compatibility is unnecessary. Use one new storage format without a migration framework. Reject old-format projects clearly and without modifying them; preserve all existing experimental projects and user work. Historical approval in other chats does not authorize this feature's execution.

## Requirements from the conversation

| ID | Requirement and final interpretation | Owner in plan |
|---|---|---|
| R01 | Configured photo destination; personal preference expressed as `project_/library`; never hardcode `library` in runtime code. Keep local configuration ignored and a portable tracked example. | T1 |
| R02 | Safely create missing configured destination and managed subdirectories when a write action needs them. Never silently replace files, follow managed symlinks, move an existing library after config changes, or fall back to another destination. | T1 |
| R03 | Top folders `Inbox`, `Photos`, `Results Preview`, `Comparisons`, with no ordering numbers. A photo folder contains original plus editable project and exports. | T1 |
| R04 | Move original from Inbox to permanent ownership without retaining a second working copy; retain its camera filename and identified sidecars. Stable, collision-safe photo identity and readable folder name. | T1 |
| R05 | One lightweight gallery image per original; basename exactly matches photo folder. Latest successfully generated result, visibly marked Draft when unaccepted. No update from slider movements or failed work. | T4 |
| R06 | Exact revision recipe plus guides/manifests/operands replace redundant settings text. Preserve all effective settings, units, execution provenance and operation order. | T2 |
| R07 | Replace masters terminology with developed images across folder, persisted identity fields, APIs and user documentation. Preserve precision/profile/coordinate identity. | T2 |
| R08 | Revisions hold text and lightweight previews only. Full-quality images/masks/edit operands live once in project-owned immutable shared assets. Never use lossy previews as reconstruction inputs. | T2 |
| R09 | Opacity-only shading reuses foreground, alpha, W and protection/support; distinct image data gets its own asset. Other effects retain dependency/stale rules. | T2–T3 |
| R10 | Reuse unchanged processing/results based on actual effective inputs and relevant execution versions, not filenames. Retain existing verified tile/session caching. | T3 |
| R11 | Deliberate submit/apply creates work; completed validated work publishes revisions. Drafts persist separately. No revision per keystroke; identical effective operations need no redundant result revision. | T3 |
| R12 | Requested main TIFF/PNG pair; additional backgrounds, transparent exports, print sizes, crops or editable export bundles only on request. Retain requested deliverables and reuse identical deliveries. | T4 |
| R13 | Focused comparison sheet plus exact panel/revision/settings/crop references. Separate panels only on request or required evidence; preserve selected native crops. Comparisons never imply acceptance. | T4 |
| R14 | Shared pinned model directories across photos; retain necessary versions for offline work; no downloads/relocation merely by opening a project. | T1, T5 |
| R15 | Inspectable expendable processing cache; first cleanup is explicit and previewed. Exclude assets, models, active jobs, resumable checkpoints and unknown ownership. | T5 |
| R16 | Clear maintained documentation, concrete behavior tests, source-backed simplicity assessment and two independent plan reviews. | All, T6 |

### Personal destination clarification

An asynchronous question asks whether `project_/library` means `<repository-root>/library` or the literal `<repository-root>/project_/library`. No answer has arrived when this draft is written. Runtime and storage design support both; the actual personal config and exact ignore entry must not be instantiated until this wording is resolved. Recommended reading is repository-root/library, giving `destination = "../library"` in `config/storage.local.toml`. Literal project_ would instead give `"../project_/library"`. This is a personal setting only, not an implementation architecture choice.

## Current code and baseline

Inspected implementation checkout: `/private/tmp/image-mask-background-appearance`, HEAD `037e8fb4f62774fc85e4fe63e5029bcca832d877`. Its local `origin/background-appearance` is `9e2b041d75ddbb8cc60702dfa7e9f2e287e4537f`; the difference is only troubleshooting documentation. No fetch. Existing uncommitted changes in four documentation files are preserved. Source hashes and exact dirty paths are recorded in `local/plans/photo-library-storage/source-baseline.json` at the planning repository root. The planning checkout itself has no application source; do not implement against its obsolete README status.

| Code anchor | Observed behavior | Decision |
|---|---|---|
| `project.py:create_project`, `_publish_new_file`, `_publish_new_directory`, `project_lock` | Original referenced externally; developed RGB16 stored once in masters; exclusive native publication, flock and state-last writes already exist. | Reuse transactions; add bounded library import wrapper and shared asset resolver, no second processing pipeline. |
| `project.py:_validate_revision_directory`, `_revision_signature` | Manifest files are revision-relative and validators/cache signatures depend on those physical paths. | Update all consumers and current validation signatures together; relocating files alone is insufficient. |
| `effects.py:run_effects`, `inherit_*`; `operations.py:_prepare`, `_matte` | Inherited full images/supports are copied with read_bytes/write_bytes into each revision. | Carry asset references, store only changed operands. |
| `effects.py:run_effects` opacity_only branch | W rebuild is already skipped, but inherited images are still copied/re-encoded. | Preserve numerical path; eliminate storage duplication. |
| `background.py`, `exposure.py`, `shadow_fade.py`, `repair.py` | Readers receive revision directories and directly open logical filenames; repair operands are essential to exact replay. | Route through one resolver; retain all operands and semantic validation. |
| `matte.py:native_matte`, `models.py:SamSession.select` | Existing content/version/backend-aware tile cache and bounded embedding reuse. | Extend only evidenced gaps; no general execution graph, new cache engine or duplicate fingerprint framework. |
| `models.py:verify_sam`, `verify_vitmatte`, `_setup_model` | Explicit verified model directories; symlinks rejected; downloads only through setup. | Share configured paths. Do not replace this with Hugging Face snapshot/symlink caching. |
| `review.py:write_review` | Default crop is entire native frame; several full-size PNG panels plus concatenated contact sheet are written per revision. | Lightweight revision overview; explicit comparison writes remain separately scoped and correctly mapped. |
| `export.py:export_project`, `publish_artifacts` | Always exports many RGB16 layers/alternate views; identical delivery checked after staging all files. | Small default result pair; opt-in variants, preflight identity check before expensive staging. |
| `viewer.py`, `ui/review.html`, `cli.py` | Shared operation APIs; explicit Apply; identity checks, pending draft protection, fixed image routes. | Preserve controls/security; wire selected options and latest-result status without a separate app. |
| `docs/file-contract.md`, `README.md`, maintained workflow docs | Detailed saved-data and failure contracts exist. | Update canonical contract; add one library usage guide, link rather than duplicate. |

## Proposed storage and naming

```
<destination>/
  Inbox/
  Photos/<photo-folder>/
    original/<camera-name and identified sidecars>
    project/
      source.json, recipe.toml, guides.json, state.json
      assets/developed/<developed-id>.tif
      assets/<sha256>.tif or .png
      revisions/rev-NNN/<text records and preview.jpg>
      requests/, approvals/, recovery/, cache/, exports/
  Results Preview/<photo-folder>.jpg
  Comparisons/<photo-folder>__cmp-NNN/<sheet and manifest; requested crops>
```

Keep logical image roles in the manifest instead of adding a physical directory per mask/effect. `assets/developed` gives developed source images an explicit role. Full-quality file formats remain existing uncompressed RGB16 sRGB TIFF and exact categorical/grayscale16 masks; no new codec/dependency or TIFF compression change.

Proposed stable photo ID is `P` plus the first 12 hexadecimal characters of source SHA-256; folder is `<photo-id>_<capture-date-or-undated>_<subject>`. This avoids a global counter/database. Verify the full hash on every ID match; prefix collision fails visibly, never aliases. Subject is a short validated filename component (Unicode allowed, no path separators/control characters, reject `.`/`..`); camera filename remains unchanged. Freeze folder basename at import. A metadata scan of published `Photos/*/project/source.json` plus validated pending import records in `Inbox/.imports/` detects a repeated full source hash. A published match returns its existing project; a pending match directs the caller to that exact import recovery record. This includes identical bytes under different camera filenames/subjects; never create a second bundle. No recurring full-image scan or global catalog. A repeated Inbox copy is left untouched and reported, not automatically deleted. Imported sidecars are preservation/provenance only; unsupported third-party edits are not claimed to be applied.

## Configuration and safe creation

One `config/storage.local.toml` (ignored), one `config/storage.example.toml` (tracked). Example destination stays `../local`; personal destination remains a local choice. `[storage].destination` is required. Optional `[models].sam_cache` and `vitmatte_cache` are justified by two existing model routes. Explicit CLI model arguments override config; config overrides existing model environment variables. Missing models fail with existing setup guidance, never trigger downloads.

Use standard `tomllib` and existing `tomli_w`; no environment interpolation, profile registry or configuration framework. Relative paths resolve against the selected config file's canonical parent. CLI `--config` explicitly selects the file; repo-root examples use `config/storage.local.toml`. An invocation elsewhere supplies that path explicitly. Missing/malformed config fails before filesystem creation; unknown keys fail visibly. Do not search arbitrary parent directories for another config.

A write entrypoint creates missing destination/managed directories after validation; read-only status/inspection never creates them. Validate all existing components as real directories, reject file/dangling-link/symlink conflicts and permissions errors. Create new private directories with 0700 without changing existing permissions. Use a small component-walk helper with directory descriptors and O_NOFOLLOW on the supported macOS platform; no standalone filesystem abstraction. Cooperative locks still do not promise protection from arbitrary hostile external writers. Check free space on the nearest existing destination ancestor before large writes. Config changes never move an old library.

Retain `/local/` ignore and add the resolved personal destination ignore plus `/config/storage.local.toml`. Update repository guidance to allow explicitly configured ignored photo storage. Verify actual ignore behavior and package contents; ignore rules do not remove tracked files. No pictures/config created in the planning task.

## Import ownership and recovery

A new library import wraps the existing decoder/create_project behavior. Only regular files explicitly selected in this library's Inbox are moved. Before any move: validate source/development inputs, hash originals/identified same-basename sidecars, check space and publish a synced import record in a private staging photo folder under `Inbox/.imports/`. Hold one library import flock throughout each import/resume, including published/pending duplicate checks, staging/decode, all original moves and final ownership publication. This intentionally serializes new imports for the single-photo workflow and avoids a reservation protocol; a concurrent importer gets a clear busy response and can retry. Malformed pending records fail closed with their recovery location; never ignore an uncertain ownership record. Reuse the existing lock helper mechanism, no scheduler. Processing of existing photos keeps independent per-project locks.

Prepare and validate the new project from source bytes before moving the original. Store its final source locator relative to project (`../original/<filename>`) with full hashes. Move source and explicitly identified sidecars using native exclusive same-filesystem moves into staged original/. Reject cross-device paths before the first move; no automatic copy/delete fallback. Publish the complete photo folder exclusively only after source hashes, destination paths and project data validate. Never clobber an existing photo folder.

If interrupted after some moves, the import record names every source/destination/hash. Explicit retry of the same import inspects both locations and either completes the exact pending import or stops on mismatch. Do not create another photo, remove uncertain remnants or guess which duplicate is authoritative. A newly created empty directory may remain after failure; existing files and originals remain recoverable. No general transaction journal service is introduced.

## Immutable assets and new format

Use storage schema 2 and `developed_id` consistently in project/source, recipe, guides, revision/request/response identities, CLI options and viewer payloads. No dual readers, migration commands or silent rewriting of schema 1. Existing old fixtures are updated intentionally, retaining assertions for unchanged image behavior; one old-format refusal test protects preservation.

Keep `manifest.files` for revision-local non-image files and small previews; add `manifest.assets`, mapping existing logical image names to `{path, sha256}`. Shared paths are project-relative under assets only. Validate hash, format, dimensions/profile and role semantics exactly as today. File-signature/semantic caches must include all referenced asset signatures before returning. Persist staged image inputs, masks, repair operands, prepared candidates and background fields via the same store. A revision's root recipe is its immutable effective snapshot; the project-root recipe remains an editable draft. In `run_effects`, synthesize every applied effect section from the validated settings actually used (cleanup, shading, exposure, fade and background), and carry unchanged sections from the parent's effective snapshot/validated manifest, not from unrelated pending draft changes. Preserve the exact consumed draft in `inputs/recipe.toml` and original request. Update only the applied sections of the project-root draft after validated revision publication, using the existing recheck/atomic-write pattern; preserve unrelated pending fields. The effects revision's `draft_digest` hashes its effective recipe and saved guides. If unrelated editable draft changes still differ, existing acceptance checks continue to block acceptance until the user applies or explicitly replaces those drafts. Restore uses the effective snapshot and retains existing explicit draft-replacement/recovery behavior. No separate settings database or second recipe format. Test request overrides, inherited settings, restore and the next operation together. Keep ordered requests, external-input text snapshots and exact model/runtime identities; no `_settings.txt`. Document each numeric unit and fraction-to-percentage conversion without rounding stored effective values (for example 0.12 means 12%).

Reuse inherited references without copying or decoding/re-encoding unchanged images. For newly computed assets, write/validate once, compute hash, publish exclusively, and reuse a matching existing immutable object. No global deduplication, reference-count database, delta images, packfiles or hardlink-based storage scheme. Existing atomic publication helpers may use native filesystem operations; that is distinct from making many revision-local asset links.

Reference validation and complete revision publication happen before state advances. A crash may leave an unreferenced valid asset; keep it. Automatic asset garbage collection is out of scope. All retained revisions and exact repair operands remain reconstructible offline with cache/models/source locator unavailable. Renaming developed-image identifiers must not alter the existing identity computation or image math. Include the `SamSession.select` argument and the required `native_matte` cache-key field in the same rename; a renamed caller with an old required cache key would silently disable reuse. Update their fixtures and maintained `docs/matting.md` examples together.

## Reuse and deliberate revisions

Keep existing stage cache keys, backend invalidation and explicit opacity/amount-only modes. Never reuse across changed source/developed identity, geometry, alpha, guides/protection, support, model/config/backend/dtype/package/preprocessing identity. Validate current base/draft and operation authorization before any fast return; stale requests remain stale.

Add a conservative no-op path for effects: compare the fully validated requested effective settings, scope, operands, candidate/lock semantics and algorithm identity with the current revision. Exact equivalence returns current revision with `reused=true`; meaningful metadata/protection/guidance changes can still create a small revision even if pixels match. Do not implement a general request replay registry. Existing matte/prepare/repair callers retain stage reuse, and existing-result reuse is only allowed where the owner proves complete semantic equivalence. Unknown dependencies mean normal computation, never guessed reuse.

Draft edits are separate from submitted operations. No new history object per slider movement. Publish only complete validated revisions. Submitted failures stay in existing request/recovery records and do not become result revisions. Failed/duplicate work cannot change acceptance.

## Result previews, export and comparisons

Define result generation as successful publication of a complete renderable matte/repair/effects revision with no stale enabled effects. Prepared-only and stale-effect stages are not final appearances; show a visible status explaining why the previous gallery result remains. No additional full-quality export is required merely to refresh the gallery. Explicit result exports still produce the requested TIFF/PNG pair.

Add `latest_result_revision` to project state independently of working/accepted pointers. A new valid result advances it; restore alone and exporting an older revision do not. First result creates one gallery JPEG; subsequent results replace that same basename. After every successful acceptance-pointer change, derive the gallery status from `latest_result_revision == accepted_revision` and refresh its footer in either direction without changing the latest image identity. Accepting the latest makes it Accepted; accepting an older restored revision makes the latest Draft if it was previously Accepted. Acceptance never advances the latest-result pointer. Reused-result fast return may repair a missing/stale preview but cannot create another file or acceptance event.

Proposed preview encoding: sRGB JPEG, maximum image long edge 1600, no upscaling, quality85/optimize, one small footer outside image for Draft/Accepted and revision. These are starting settings for human visual checking, not a measured quality guarantee. Preserve aspect ratio and label reduced precision. Produce revision preview and gallery view with the same renderer; do not copy source EXIF/GPS into previews.

Use per-project lock, existing atomic file replacement and a single project-local `preview.json` receipt containing revision/manifest digest/gallery basename/status. No global gallery database or watcher. New result generation publishes state first, then preview atomically, then receipt; failure preserves the prior preview and reports `preview_pending`. Acceptance changes need a different order: before any change of accepted revision, durably write a Draft-labelled preview of the current latest result under the same writer lock. This also handles a stale or uncertain old receipt without trusting its claimed footer. If demotion or its directory sync fails, do not change acceptance. Then commit acceptance state; promote the latest footer to Accepted only after that state commit succeeds and only when the latest and accepted pointers match. If state publication or later promotion/receipt fails, retain the conservative Draft/pending display, reread actual state for reporting and never claim rollback merely because sync returned an error. Immutable revision previews and accepted result assets are untouched. This ordering permits an accepted image to remain visibly Draft pending repair, never an unaccepted image falsely labelled Accepted. Next explicit open/result/status-repair action can rebuild from current authoritative pointers after revalidation. No claim of multi-file atomicity. Read-only status reports mismatch without writing. A reader/crash cannot make an older worker replace newer results because publication rechecks the authoritative latest pointer under the project lock.

Default explicit export is chosen Result RGB16 TIFF plus PNG8 view and compact manifest/recipe. Additional `black`, `transparent`, `editable` variants are requested explicitly; current complete layer export becomes the editable option. Preserve accepted-versus-draft authorization. Export identity binds revision manifest, requested variants and encoding version. Check a complete existing matching export before rendering/staging; any file/hash mismatch fails without overwrite. Different requested sets get distinct identity-labelled directories. Failed temporary outputs remain diagnosable, not hidden as success.

`Comparisons` contains a comparison sheet plus manifest linking panels to exact saved revision, settings, native crop, displayed dimensions and transform. Explicit retained evidence crops can be native PNG there, not in revisions. UI on-demand native views stay available without writing panel files. Assisted review currently depends on crop metadata and hashes: preserve bindings and inspected-coordinate validation while separating its requested evidence bundle from the small automatic revision overview. No automatic palette generation for every operation; comparisons never count as accepted results.

## Cache, models, documentation and limits

No model downloader/cache replacement. Configure existing hash-pinned model directories once; retain versions needed by retained work, outside disposable processing cache. Exact saved-layer reconstruction requires no inference; fresh inference is not promised bit-identical across environments.

First cleanup scope is only project-owned `cache/matte` entries under the project lock. Read-only inspection reports sizes, protected reasons and candidate files. For simplicity, any incomplete/resumable or unrecognized request record blocks cache deletion for that project; do not invent fine-grained checkpoint reachability. Explicit apply requires the exact inspected candidate-list digest, rechecks current files/request records, and deletes only matching recognized expendable entries. Preserve backend marker, model paths, requests, revisions, shared assets, outputs, staging diagnostics and unknown files. No timer, quota, age policy, recursive root cleanup or asset GC. Deletion permission is separate from this plan's approval.

Maintain `docs/file-contract.md` as normative saved-data owner; add `docs/library.md` for configuration, naming/import, preview/export/comparison, offline model locations, disk inspection and backups. Update README, workflow, assistant workflow, guidance, matting, troubleshooting, model provenance and repository guidance only where this change alters their claims. The frozen v4 document remains historical; add a clearly linked current amendment in maintained docs/coordinated plan so obsolete storage details are not presented as controlling current behavior. Do not copy private paths/photos into public artifacts.

## Validation and public references

Use small synthetic images and existing offline test fixtures. Required coverage includes real two-process locks, failure before/after source move, state-last failure, asset corruption/different references, unchanged RGB16/partial alpha/protection, no-inference opacity edit, saved-only reconstruction, correct crop transforms, gallery failure/recovery, repeated export and cleanup exclusions. No installation, model evaluation, photo upload or private-source tests are required to write/review this plan.

Official references checked 2026-10-19: [Python 3.12 pathlib](https://docs.python.org/3.12/library/pathlib.html#pathlib.Path.mkdir), [Python filesystem operations](https://docs.python.org/3.12/library/os.html#os.replace), [TOML reader](https://docs.python.org/3.12/library/tomllib.html), [Pillow JPEG encoding](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#jpeg). Context7 CPython material confirms dir_fd/O_NOFOLLOW APIs; version-specific claims use 3.12 documentation. `mkdir(exist_ok=True)` alone is not a symlink/publication policy; `os.replace` is for the replaceable preview/state, not immutable originals/assets. No dependency changes proposed.
