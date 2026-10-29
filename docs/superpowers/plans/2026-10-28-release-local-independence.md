# Release local-directory independence implementation plan

> **For agentic workers:** Use `superpowers:executing-plans` for native execution, or `superpowers:subagent-driven-development` only if the user selects delegation. Read this entire plan before starting; checklist steps record execution evidence, not implied approval.

**Goal:** A fresh checkout can be set up and used with no pre-existing `local/` directory, and this workspace can retire almost all development material under `local/` without losing photographs, accepted work, unique code or useful personal references.

**Architecture:** Keep the existing explicit project/library/model paths and reproducible Python environment. Remove developer-tool and documentation assumptions about `local/`; preserve personal data separately from disposable development artifacts. Prove the documented workflow in an isolated checkout before retiring the old runtimes and source copies.

**Tech stack:** Existing native macOS ARM64, Python >=3.12,<3.13, hash-locked pip requirements, setuptools, pytest and the optional existing Chrome/Playwright lane. No new dependency, installer framework, catalog service or automatic cleaner.

**Spec:** The user's 2026-10-28 request to clean confirmed disposable material now and plan operation as a fresh clone with nothing relying on `local/`; the scope, constraints and acceptance criteria below; existing contracts in `README.md`, `docs/library.md`, `docs/file-contract.md` and `docs/assistant-workflow.md`.

**Status:** Reviewed for implementation on 2026-10-28. The user has requested plan correction, implementation in a new GPT-6.1 Sol chat, then independent review and fixes. That request authorizes the bounded local code/documentation work and verification below. Only the initial cleanup and its historical-evidence note have executed at this review checkpoint; setup, implementation, data relocation and further deletion remain unperformed. Downloads, new interpreter installation, private-data relocation and exact deletion manifests retain their separate approval gates. No commit, push, publication or production authority is included.

## Scope and current evidence

- Inspected local `main` at `5f6eea51697332524279ca733fba8dc14df22bcd`, ahead of its existing `origin/main` by one commit, with no tracked working changes before this plan. No remote refs were refreshed; preserve that existing commit and all later user work.
- `src/blackmask/` has no discovered literal dependency on `local/`, private home paths or development worktrees. This is static evidence, not fresh-install proof. Packaging discovers `src/` packages; `MANIFEST.in` explicitly prunes `local/` and private library data.
- `config/storage.example.toml` selects `../local` and its commented model examples use `../local/models/...`. The real ignored configuration currently selects a different existing destination inside the checkout and existing models outside it. Do not change the real configuration just to match new examples.
- `tests/run_browser.py` hardcodes both `local/browser-runtime` and `local/browser-runs`. `requirements-browser-macos-arm64.lock` and `docs/validation.md` describe those paths. Browser dependencies are intentionally separate from the application environment.
- `docs/assistant-workflow.md` fixes the optional personal reference catalog at `local/references/README.md`. Reference folders are already self-contained and private; they are not prerequisites for a new user's manual workflow.
- Pilot `.command` files reference a retained runtime and source checkout under `local/reviews/`, plus old project paths. Several referenced flower, dragonfly and spider project/library paths no longer exist. Locate the corresponding live data or verified backups rather than treating old guides as proof of ownership.
- `local/reviews/coderabbit-pass/` contains nine embedded Git repositories. One inspected implementation checkout was clean on `local-sharpening`; the remaining checkouts and unique refs/commits have not been cleared for deletion.
- At the initial audit, two pilot projects recorded accepted `rev-007`; `photo-tests/` included an original DNG and developed photo data. Their later explicit discard is recorded below; these were user data, not disposable cache.
- The root currently has no usable `.venv/bin/python`, and `python3.12` is absent from PATH. Do not delete the retained runtime until a replacement has actually passed the relevant checks. This observation does not establish whether Python 3.12 is installed elsewhere.

### Initial cleanup completed

Removed `local/series-framing/`, `local/source-appearance-workflow-1792617287884371000/` and the directly identified Finder `.DS_Store` files in `local/`, `local/pilots/` and `local/reviews/`. The series folder's own `.DS_Store` was included in its removal.

The preflight verified synthetic-source provenance for every series source record, no Git repositories/runtimes/symlinks or special entries in those targets, no tracked files under `local/`, stable inventory and available existing project writer locks. Removed **1,519 files / 421,801,532 logical bytes**. Logical bytes are not a measurement of physical space reclaimed. The detailed deletion manifest is retained outside the checkout in temporary storage.

`series-framing/` was historical development evidence, not an operating dependency. Its old raw logs are now unavailable; the existing tracked validation narrative remains a historical account, not a rerun or a requirement to recreate that folder.

## Global constraints and proposed choices

- Support native macOS ARM64 and Python >=3.12,<3.13; preserve existing dependency and model pins. Recreate environments from the lock, rather than relocating the retained virtual environment.
- A fresh installation must not read from, create or require a repository `local/` directory during the supported setup/manual workflow. Explicitly selected user paths remain supported, including existing libraries that happen to be under `local/`; do not ban or migrate them automatically.
- Preserve the current explicit TOML configuration contract: no automatic configuration search, destination fallback, new storage schema, silent path rewriting or automatic model download.
- Proposed example: use an explicitly selected photo-library path such as `/path/to/photo-library` and independently selected model paths. The setup instructions must tell the user to replace placeholders before initializing storage.
- Proposed optional browser interface: `--packages PATH` is required; `--evidence-root PATH` is optional. Default evidence goes in a fresh standard-library temporary directory, with its path reported. These options do not exist yet. Preserve isolated packages, loopback-only network access, write containment, timeout handling and diagnostics.
- Personal launchers are convenience files, not an installation requirement. Recreate retained ones against the canonical installed command, actual live project/config and selected models; retire obsolete launchers with their abandoned examples.
- Keep personal references in a user-selected directory. The assistant receives its explicit catalog path with the task; absent personal references must not block ordinary manual use. Reuse portable appearance recipes and framing presets instead of building a new catalog system.
- No original, accepted dependency, recovery journal, private reference, unique patch or unpreserved Git state is disposable. Move/copy only under an approved exact manifest, verify before removing old copies, and retain recovery where relocation cannot yet be proved safe.
- Keep this work bounded to local-directory independence and cleanup. No release-version bump, feature redesign, platform expansion, new release pipeline, dependency refresh or broad rewrite.
- The current request authorizes implementation and orchestration in a new GPT-6.1 Sol chat. Existing installed interpreters and local package inputs may be inspected and used for bounded verification. New interpreter installation/downloads, private-data destinations/relocation and deletion require concrete proposals and the applicable explicit approval. No commits, pushes, review replies or PRs are included.

## Approaches considered

1. **Recommended: reproduce the existing explicit setup, repair the small number of path assumptions, then retire development material.** Keeps the current storage/runtime architecture and gives a fresh-clone proof with limited code changes.
2. **Only move `local/` elsewhere.** Frees that directory name but leaves borrowed runtimes, stale launchers and hidden dependencies; does not meet the requested outcome.
3. **Build automatic application-data discovery, migration and installation.** Larger public-interface and recovery change than needed. Reconsider separately only if the existing explicit setup proves insufficient.

The review selects approach 1 within the user's implementation request. This does not select personal-data destinations or approve destructive actions.

## Execution order and ownership

The implementation chat owns Tasks 1–3 and the pre-deletion portion of Task 5. The orchestrator owns independent review, disposition decisions and coordination of fixes. Preserve the pre-existing `docs/validation.md` cleanup note, this plan and unrelated photo-directions planning files; compare implementation against a recorded pre-dispatch baseline rather than attributing every working-tree change to this task.

Start Task 1 with interpreter/package discovery. A setup or download gate does not block independent runner/documentation edits in Tasks 2–3; finish those and report the exact verification still blocked. Recreate environments from verified wheel inputs where available, using pip's `--no-index --find-links` with the existing hash/binary constraints for offline installation. Do not copy installed site-packages or call a borrowed runtime proof of independence. Preserve any existing `.venv`; use an owned fresh path if it already exists.

Task 4 inventory can run read-only while code work proceeds. Run Task 5's fresh-source/package/isolation checks on the settled candidate before proposing final deletion. Task 4 relocation, launcher edits and deletion wait for their exact destination/manifest approvals; Task 5's last post-deletion check follows them. Report implementation readiness and cleanup completion separately when any gate remains open. Independent review and material fixes must finish before declaring the implementation ready.

## Review focus

1. Missing old checkout/runtime: commands must use the newly created environment and exact candidate, without inherited `PYTHONPATH` or fallback to `local/`.
2. Different working directory and spaces in paths: explicit config/project/model/browser inputs must resolve correctly without accidental storage under the checkout.
3. Copied or relocated photo data: accepted state, originals, masks, exports and recovery dependencies must remain usable; pending imports keep their matching original configuration until explicitly resolved.
4. Missing optional browser or reference setup: actionable diagnostics and no writes to `local/`, implicit downloads or guessed personal recipes.
5. Retired development copies: preserve unique Git commits/index/worktree/untracked bytes and frozen source/reference material before deleting their only recoverable copy.

## Task 1: Establish the independent application environment and baseline

**Files:** Read `README.md`, `requirements-macos-arm64.lock`, `pyproject.toml`, `src/blackmask/cli.py`, `src/blackmask/library.py`, `tests/test_cli.py`, `tests/test_library.py` and `tests/test_library_storage_journey.py`. Change application code only if verification demonstrates an in-scope product defect.

**Interfaces:** Consumes the exact candidate source and existing lock. Produces a recorded interpreter/package/source identity and a usable canonical installed `blackmask` command without the borrowed runtime.

- [ ] Locate a supported native Python 3.12 interpreter. If absent, report the setup requirement and obtain installation authority; do not silently use the system Python 3.14 or copy the old environment.
- [ ] In a fresh environment, execute the existing README setup with `rtk proxy`: `python3.12 -m venv .venv`, then `.venv/bin/python -m pip install --require-hashes --only-binary=:all: -r requirements-macos-arm64.lock`, then `.venv/bin/python -m pip install --no-build-isolation --no-deps -e .`. Any package/network setup needs its applicable authorization. Substitute the verified interpreter path if it is not on PATH.
- [ ] Run `rtk proxy .venv/bin/python -m pip check` and `rtk proxy .venv/bin/blackmask doctor`; retain actual exits, platform and dependency diagnostics. Assert the imported application comes from this candidate and no path under the retained review/runtime tree appears in imports.
- [ ] Reuse the existing CLI, explicit-configuration and storage-journey tests for baseline behavior. In particular retain `test_explicit_config_initializes_same_private_library_from_two_working_directories` and `test_configuration_read_only_paths_are_bound_to_config_parent`; do not add source-text tests that merely forbid the string `local`.
- [ ] Record relevant baseline failures separately from cleanup. Do not delete the old runtime on setup failure or treat skipped live-model checks as passes.

## Task 2: Make optional browser tooling independent of `local/`

**Files:** Modify `tests/run_browser.py`, `requirements-browser-macos-arm64.lock` comments only, and the browser-setup section of `docs/validation.md`. Create `tests/test_run_browser.py` for observable runner behavior; reuse `tests/test_lifecycle_browser.py` for the actual browser journey. Update `MANIFEST.in` only if a checked sdist omits an input actually required for the supported source-distribution test workflow.

**Interfaces:** Keep `main()` as the script entry point; it reads the proposed `--packages PATH` and optional `--evidence-root PATH` arguments through standard-library argument parsing. The subprocess uses the selected packages and a fresh reported workspace, preserving the existing isolation contract. No application CLI/schema changes.

- [ ] Add failing runner tests for explicit package/evidence paths containing spaces, omitted evidence root using fresh temporary storage, and missing/invalid Playwright setup failing before a browser launch or unintended directory creation. Make subprocess assertions cover the existing sandbox/network/timeout behavior without executing arbitrary receipt scripts.
- [ ] Make prerequisite validation actionable for an incomplete selected package directory, not merely an existing `playwright/` directory. Test that selected package resolution is used rather than an ambient installation. Keep validation local and bounded; do not add a dependency installer or expand process-supervision scope.
- [ ] Implement only the argument/path handling needed by those tests. Never fall back to `root/local`; do not remove the separate browser package boundary or install/download from the runner.
- [ ] Replace the hardcoded browser paths in instructions and lock-file comments. Document the new proposed invocation only when it is implemented; use an explicit package target and an optional evidence directory outside `local/`.
- [ ] Run `rtk proxy .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_run_browser.py`; require the failure-to-pass evidence for the changed runner behavior.
- [ ] With separately authorized browser package setup and existing Chrome, run the real browser lane through the new interface. Verify evidence is reported in the chosen location, the intended application is imported, existing timeout cleanup of the owned process group is preserved and `local/` remains absent. Operator-interruption cleanup is not established by the existing runner and must not be claimed as preserved or verified; process-supervision changes require a separately agreed scope. Static/subprocess-stub checks do not replace this real-browser check.

## Task 3: Finish the fresh-user documentation and package contract

**Files:** Modify `config/storage.example.toml`, `README.md`, `docs/library.md`, `docs/assistant-workflow.md` and affected parts of `docs/validation.md`. Check `docs/workflow.md`, `docs/guidance.md`, `docs/file-contract.md`, `docs/troubleshooting.md`, `MANIFEST.in` and `pyproject.toml` for affected drift; edit only where needed.

**Interfaces:** Preserve `StorageConfig`, `load_storage_config(path)` and current config-relative path resolution. The optional named-reference workflow accepts the catalog path supplied in the user's task instead of assuming a repository folder. This is a documentation/workspace convention, not a new executable configuration key.

- [ ] Replace the sample storage/model destinations under `local/` with clearly explained user-selected paths. Preserve existing configuration files and all existing explicit path support.
- [ ] Explain the three locations a new user supplies: installed application environment, photo project/library, and explicitly installed pinned models. Optional personal references and developer/browser evidence are separate. Do not make historical pilots, assistant history or a paid service prerequisites.
- [ ] Update reference-catalog lookup to use the user's selected photo workspace/catalog path. Preserve aliases and self-contained card contents when moving an existing catalog. Missing references remain an explicit limitation for that requested named look, not a failure of ordinary editing.
- [ ] Retain/check the cleanup note already added to `docs/validation.md`, marking removed series-framing raw artifacts as retired historical evidence. Retain truthful historical observations and their limits; remove any remaining suggestion those files are current prerequisites or can still be opened here. Do not rewrite historical plans merely to erase old paths.
- [ ] Check all maintained setup/workflow examples and affected links against implemented help, relative-path semantics and real package contents. No new configuration-only or source-text tests are needed; exercise the existing application-path tests and the fresh-install checks below.

## Task 4: Preserve user data and retire the remaining development tree

**Disposition — 2026-10-28:** The user chose “Keep legacy material in place,”
then separately approved deleting `local/evaluations/`, `local/plans/`,
`local/examples/` and 31 listed historical planning files, and moving the existing
reference catalog/cards to root `references/`. Those bounded actions are complete.
The later exact review-storage retirement was separately approved and completed
as recorded in the follow-up below, superseding retention of `local/reviews/`.
The user then separately approved deletion of all `local/photo-tests/` and
`local/pilots/`, including their original and accepted photo data; that removal is
complete. Root library/reference data remain unchanged. Any further deletion
still requires its own exact manifest and approval.

**Files:** Private inventory/receipts outside tracked source; existing ignored storage config, reference catalog, selected personal launchers and selected `local/` subtrees only. No blanket recursive deletion of the remaining `local/` tree.

**Interfaces:** Consumes the working replacement environment, a reviewed disposition manifest, verified destination(s) and a stopped-writer window. Produces preserved photo/reference/code state and an exact list of remaining or deleted artifacts.

- [ ] Classify each remaining subtree as generated scratch, runtime, Git/source state, photograph/project/recovery, personal reference or still unknown. The generated packaging inventory already found 45 candidate build/dist/extraction directories under evaluations, approximately 38 MB logical; revalidate before deleting rather than treating that inventory as permission or proof of inactivity.
- [ ] Reconcile stale pilot links against the actual configured library and verified backups. Compare complete dependency/file hashes, accepted/working pointers, original/sidecar ownership and delivery reconstruction before calling an apparent photo-project duplicate disposable. Preserve the two accepted pilot projects and the original DNG until their verified retained location is established.
- [ ] Prefer the existing chosen library or another explicitly selected durable directory for retained personal data; it need not be moved merely because it is inside an ignored `library/` directory. For an authorized copy, retain every original, dependency, recovery record, config and permission needed to recover. Validate a copy first, retain the old copy until checks pass, and never hand-edit saved identities to force relocation.
- [ ] Pending imports and uncertain transactions retain their original configuration and destination until resolved through supported recovery. Completed-library relocation also needs rehearsal with `validate_library_project` and actual reopening/reconstruction. If the current contract cannot safely relocate a case, report that bounded blocker; do not introduce a migration format under this plan.
- [ ] Copy any retained personal reference folders/catalog to the selected independent location and verify complete hashes/internal links. Preserve frozen reference bytes. Update only the catalog location/links that actually require it.
- [ ] Inventory all refs, commits, staged/unstaged changes and untracked files in each of the nine embedded Git repositories. Prove the material is retained in canonical history or a tested private recovery archive, including index/worktree/untracked bytes. A clean worktree alone does not prove there are no unique commits. No reset, stash or loss of existing state.
- [ ] For retained pilot launchers, point to the independently installed command, verified live project/config and selected models; remove dependency on review checkouts, their runtime and removed project paths. Verify the complete command on a protected copy without changing real photographic acceptance. Do not preserve obsolete launchers solely to keep abandoned checkouts alive.
- [ ] After Task 5 passes and writers are stopped, present the exact final deletion manifest and obtain the applicable deletion approval. Remove verified obsolete builds, synthetic fixtures, retired environments, redundant source copies and discarded historical logs. Archive only unique or deliberately retained material; old raw logs are not mandatory runtime assets. Confirm target absence and retained hashes, reporting anything still protected or unresolved.

## Task 5: Prove the clone-equivalent workflow and final disposition

**Files:** Reuse existing CLI/library/export/storage/browser tests, adding application-path regressions only for a demonstrated uncovered dependency. Keep one small final verification/disposition record outside disposable scratch; summarize the maintained contract in `docs/validation.md` without personal paths or private photos.

**Interfaces:** Consumes the settled candidate, a clean source export and explicit test assets/setup. Produces evidence that deleting development `local/` contents does not prevent installation or supported use. This task gates Task 4's final deletion.

- [ ] Create a fresh source export of the exact candidate into isolated temporary storage, including the intended uncommitted product changes and recording their hashes. Copy no ignored runtime, `local/`, personal configuration, model, photo, Git metadata or private reference. Do not require a commit merely to test the candidate.
- [ ] Set up the supported environment from documented inputs. Clear inherited `PYTHONPATH` and `BLACKMASK_*` settings, redirect HOME/cache/temp to owned storage, and deny access to the original checkout/review source/runtime paths during application execution. Give only the explicitly selected fixture/model inputs the access they need; no implicit model/network access after setup.
- [ ] Separate direct isolated CLI/package checks from tests that already create their own native sandbox. `docs/validation.md` records that macOS rejects nested `sandbox-exec`; run the full suite and storage journey directly in the fresh exported environment, and run the independent CLI/wheel probes under their own access-denial policy. Prove the latter policy with rejected read/network controls and record its scope. Absence of a newly created `local/` directory alone does not prove that no old path was read.
- [ ] From a different working directory, use the installed CLI to initialize an explicit independent library, import a synthetic source and sidecar, open/status the project, exercise the existing deterministic prepare/matte/repair/accept/restore/export journey, and reconstruct exported editable assets in a fresh process. Reuse `tests/test_library_storage_journey.py`; synthetic/stub inference is not real-model or photographic evidence.
- [ ] With actual installed pinned model assets only when authorized, separately verify the documented real prepare/matte path. Missing models must fail actionably without downloads. If this lane cannot run, report exactly which real-model startup/processing behavior remains unverified; do not equate stub success with a complete new-user processing check.
- [ ] Build and inspect the actual wheel and sdist from the candidate using the established installed setuptools backend. Check their member bytes/metadata for private paths, photos, references, Git/local/planning material and undeclared dependencies. Verify UI assets and installed example config in the wheel, and maintained docs, locks and required test helpers in the sdist according to `pyproject.toml` and `MANIFEST.in`; do not invent a requirement that the wheel contain the full source test/documentation tree. Test a regular wheel installation in its own fresh environment from a different working directory, with source/review/local access denied, so an editable install cannot hide missing packaged assets.
- [ ] On the settled candidate run the documented full relevant suite once: `rtk proxy .venv/bin/python -m pytest -q -p no:cacheprovider`; `rtk proxy .venv/bin/ruff check src tests --no-cache`; `rtk proxy .venv/bin/ruff format --check src tests --no-cache`; `rtk proxy .venv/bin/mypy src`. Retain actual exits/counts/skips; reuse unchanged successful evidence. Run the real browser check from Task 2 on the same candidate where applicable.
- [ ] Record which installation/application/browser paths were actually exercised without `local/`, with imported source identities and access-denial evidence where available. Distinguish directory-absence observations from enforced read isolation; do not extend either claim to unexercised paths. Verify retained photo/reference data for every authorized relocation/deletion. Report automated, real-browser, real-model and human acceptance separately; this housekeeping work grants no new photographic acceptance or blanket v1 readiness.
- [ ] After final approved deletion, verify the replacement workflow still runs against preserved data without restoring old scratch. Record the small final retention/disposition summary; do not accumulate another permanent copy of every failed/intermediate artifact.

## Completion criteria

- Documented fresh setup and ordinary use work with no pre-existing repository `local/` directory or borrowed runtime/source tree.
- Optional browser tooling and reference lookup have explicit independent locations; their absence has the documented bounded effect.
- Existing explicit paths, saved projects, acceptance, precision, recovery and offline-after-setup behavior remain supported without a schema change.
- Unique personal data/code is preserved and verified before old copies are deleted; every retained remainder has a concrete reason.
- Almost all development `local/` contents can be removed. Prefer an absent/empty directory after preserved personal data is relocated or verified elsewhere; no arbitrary byte/percentage target overrides preservation.
- Current documentation accurately states what was demonstrated, what was retired and what remains unverified. No Git publication or version/release action is implied.

## Current external guidance checked on 2026-10-28

- [Python 3.12 venv documentation](https://docs.python.org/3.12/library/venv.html): recreate environments rather than moving/copying them; preserve the repository's stricter Python/platform bounds.
- [PyPA environment and pip setup guide](https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/): isolated reproducible application environment.
- [pip secure installs](https://pip.pypa.io/en/stable/topics/secure-installs/) and build-isolation guidance, also retrieved through Context7: retain hash checking and binary-only dependency installation; `--no-deps` prevents dependency resolution and `--no-build-isolation` requires build dependencies to be installed already.
- [pytest temporary directories](https://docs.pytest.org/en/stable/how-to/tmp_path.html): generate synthetic fixtures in owned temporary workspaces; preservation/retention remains explicit.

These sources inform the proposed verification approach. They do not establish this project's installation, model, browser, migration or photographic results.

## Plan check

Self-review and one independent read-only builder check covered the proposed scope against its owning code, configuration, packaging, reference and journey contracts. The independent check identified an incorrect assumption about existing operator-interruption cleanup; Task 2 now preserves the implemented timeout behavior and explicitly leaves operator interruption unverified. No runtime, browser, model or migration execution was performed for this plan check.

The subsequent implementation-readiness review corrected stale authorization wording, made setup-independent work and pre/post-deletion ordering explicit, separated native sandbox checks to avoid the documented nested-sandbox failure, required incomplete-package/ambient-resolution coverage, and aligned wheel/sdist checks with their actual packaging contracts. Python venv and pip secure/offline installation guidance was rechecked through official documentation and Context7. These are plan corrections; execution evidence must be recorded separately.

## Execution evidence — 2026-10-28

Bounded implementation and pre-deletion verification ran in the dispatched checkout,
preserving the existing commit, historical validation cleanup note and unrelated
untracked planning files. No application schema/runtime behavior was changed beyond
the optional browser runner; no Git writes, private-data relocation, launcher edits
or deletion were performed. The owning orchestrator's independent read-only review
reported **No material improvements recommended** for the settled source/test/docs
scope. Later edits only record evidence and clarify retired historical records.

- **Task 1:** Found installed native ARM64 Python 3.12.14 outside the retirement
  tree. Created a new `.venv` from that base interpreter, then installed all 41
  application-lock wheels offline with hash/binary constraints, followed by the
  editable candidate with no build isolation/dependency resolution. No installed
  environment/site-packages was copied. `pip check` and `blackmask doctor` exited
  0; import identity points to this candidate with no retained-runtime import path.
- **Task 2:** Added required `--packages` and optional `--evidence-root`, isolated
  import/driver preflight before evidence creation, fresh default temporary storage
  and no `local/` fallback. Initial regressions: 9 failed before implementation;
  an additional ambient-Node regression then showed 2 failed/8 passed before its
  fix. Final runner tests: **10 passed**. Timeout/process-group behavior is covered
  with subprocess doubles; operator interruption remains unverified.
- **Approved browser lane:** Direct human approval was relayed by the orchestrator
  for exactly three missing locked PyPI wheels and synthetic Chrome verification.
  Downloaded only Playwright 1.64.1, pyee 14.0.0 and greenlet 3.5.6; combined them
  with cached locked typing_extensions in a fresh separate target. Hashes match
  the browser lock. Chrome 156.0.8078.48 / Playwright 1.64.1: **1 passed**, exit 0,
  61.50 seconds. Native network/outside-write and browser external-network controls
  passed; the exported checkout had no `local/`. A preliminary download command
  retained offline flags and failed before downloads; the approved scoped PyPI
  command then succeeded. No private profile or photograph was opened.
- **Task 3:** Updated the storage/model example, setup/library instructions, explicit
  optional reference-catalog convention and browser instructions. Checked workflow,
  guidance, file/recovery contracts, troubleshooting, package declarations and
  maintained local link targets; no additional behavior/schema changes were needed.
  Preserved the historical cleanup note and clarified that retired raw records are
  no longer available. Existing private configuration/catalog bytes were untouched.
- **Task 5 deterministic checks:** The final fresh-export suite exited 0:
  **2,677 passed, 7 skipped**, 1,684.99 seconds. This includes the explicit-config
  and full synthetic storage/reconstruction journeys. Ruff check/format exited 0
  (69 files formatted); Mypy exited 0 (29 source files). The seven optional-input
  skips do not supply private-photo/I10 recovery or human-acceptance evidence.
- **Isolation evidence:** Separate editable and regular-wheel CLI probes from a
  different working directory initialized/imported/reopened an explicit synthetic
  library with sidecar hashes preserved. Both passed Python/native C read-denial
  controls against the original checkout and a network-denial control; the wheel
  probe also denied exported source reads. Installed UI/config assets were readable.
  Full-suite execution itself was not run inside an extra native sandbox.
- **Verification environment limits:** The initial focused baseline had 295 passed
  and 5 failed solely at native `sandbox_apply: Operation not permitted` inside the
  tool sandbox. An initial full run was interrupted, incomplete, with wrapper exit
  130 and no captured underlying pytest exit/counts. Its owned processes were
  confirmed stopped before final evidence was accepted. The successful final suite
  ran outside the tool sandbox against the settled runner/test hashes.
- **Approved model lane:** One real 64×64 synthetic RGB16 CLI prepare+matte journey
  used existing explicit pinned SAM/ViTMatte caches on CPU after the full suite
  finished. Exit 0 in 22.11 seconds, no timeout under the 300-second process-group
  cap; observed child macOS `getrusage` max RSS 1,926,250,496 bytes. Three SAM
  candidates and one inferred matte tile were recorded, source hashes preserved,
  acceptance unset, with networking/original-checkout reads denied. OpenMP emitted
  temporary-file size warnings in both stages; both commands still exited 0. No
  model download or private-photo inference occurred. This is bounded runtime
  evidence, not photographic quality, recovery coverage or a general RAM bound.
- **Package evidence correction:** The initial export omitted tracked planning
  files, so that first build could not prove their pruning. Added all 51 omitted
  tracked files, including planning/agent-only material, without changing tested
  application inputs. Final packaging is rebuilt after the evidence documentation
  against these actual source bytes; archive inspection checks UI/config, maintained
  docs/locks/test helpers, metadata dependencies and excluded/private material.

Detailed command logs, source/member hashes, package inspection and the small
verification summary are retained in the external temporary evidence workspace
`release-independence-nmuuih8q`; the implementation handoff provides its absolute
path. Relevant logs include `runner-red.log`, `ambient-driver-red.log`,
`runner-final.log`, `baseline.log`, incomplete `full-suite.log`, successful
`full-final.log`, `lint-final.log`, `format-final.log`, `mypy.log`,
`real-browser.log`, `real-model.log` and `real-model-exit.json`.

**Initial Task 4 checkpoint — superseded by the later explicit dispositions below.** Inventory
found legacy accepted pilot projects using schema 1, while current project
reader/lock APIs require schema 2; a separate schema-2 library project does not prove
legacy accepted edits are duplicated. The user's later exact-scope approval removed
the three local folders and 31 historical planning files described above. The
reference catalog/cards moved to root `references/`, retaining their structure,
recipes and image bytes; only the catalog's relative documentation link changed.
At that checkpoint, legacy projects, embedded Git state and photo launchers remained
in place. No saved-project migration or real storage-configuration change occurred.
Remaining development storage is not declared disposable, and neither cleanup nor
software verification supplies photographic acceptance or blanket release readiness.

Cleanup checks passed: all 31 approved document removals and three folder removals
match the scope; 110 unaffected baseline files retain their hashes, and 2,434
retained photo/library entries retain their metadata. All 281 checked local links
resolve. All 14 private reference files are ignored, while the folder and empty
placeholder remain eligible for Git. Rebuilt wheel/sdist inspection excluded the
reference directory and synthetic private-content sentinels; a regular wheel
installation initialized a temporary library successfully. The first smoke command
used macOS's `/var` symlink and was rejected by the existing path contract; the
corrected physical-path invocation passed without a production-code change.
Unchanged application tests were not repeated for this filesystem/documentation
cleanup. Command logs and exact manifests remain in the temporary cleanup receipt.

## Review-directory retirement — 2026-10-28 follow-up

**Goal:** Remove active dependencies on `local/reviews/`, preserve photo data and
present the exact source/Git loss for approval. The user intends to discard unique
work and the temporary archive too, after reviewing the exact scope. The user
approved preservation and exact deletion; both deletion roots are now absent. No photo/schema migration, acceptance,
application/dependency change, model run, Git write or external action is included.

### 1. Inventory and recovery limits

- [x] Inventory all review entries without following symlinks: 1,065,695 regular
  files / 4,445,214,096 logical bytes; 368,636 directories; 6,200 symlinks; 79 special
  entries. No traversal errors. Inspect all nine embedded repositories: 66 changed
  path entries and nine distinct commit IDs absent from canonical local refs/HEAD.
  This does not prove absent functionality or remote uniqueness.
- [x] Create the authorized temporary recovery directory and attempt the full
  native archive. The attempt exited 1: one permission-denied file and seven
  unsupported extended-attribute warnings. It remained `.partial` until the approved
  deletion; no permissions were changed or complete recovery claimed. Inventory records 18 mode-000
  evidence files. No complete archive validation or restoration claim is made.
- [x] Revise the original recovery-first gate to match the user's later intent:
  prepare explicit intentional-discard approval, disclosing the failed backup.
  Neither a partial archive nor a successful listing authorizes deletion.

A Git bundle alone omits local index/worktree state; no bundle, commit, stash,
reset or ref change substitutes for the user's exact-discard decision. The temporary
archive was outside runtime paths and was never an independent-device backup.

### 2. Remove live dependencies

- [x] Replace the two private pilot launchers' obsolete runtimes/source paths with
  the installed application. Clear inherited `PYTHONPATH` and preserve offline
  flags. Both recorded project targets were already missing; stop before launch
  with an actionable message, without creating or substituting a project.
- [x] Copy 61 dragonfly/spider acceptance records (536,795 bytes) beside their
  pilot guides. Verify hashes/modes/mtime; retain origin manifests and all frozen
  bytes. Update live receipt links and the spider's verified root-library paths.
  Mark missing flower/dragonfly assets explicitly; receipts do not restore them.
- [x] Pass eight bounded checks: two syntax checks, two actual missing-target
  exits, two synthetic creates and two installed-CLI dispatches. Runtime checks
  deny networking, review-directory reads and repository writes. Synthetic dispatch
  adds `--headless` only through a scratch wrapper; it is not a private-photo UI test.
  All 2,152 protected preexisting photo-file metadata entries remain unchanged.
  Fourteen updated guide links resolve; source/test/config paths have no review
  dependency. No full application suite rerun is needed for this non-app change.

### 3. Exact approval and retirement

- [x] Prepare an exact entry inventory, nested Git loss report, archive identity
  and photo-preservation manifest. The approved preview and completion receipt remain
  in the temporary packet linked from the owning conversation; the recovery
  directory itself has been deleted.
- [x] Independently review the bounded safeguards, evidence limits and approval
  preview. Outcome: “No material improvements recommended.” The reviewer verified
  all 61 receipt pairs and 386 preservation candidates against live files, plus
  Git/photo states and approval boundaries. The user subsequently approved the
  exact preservation and deletion sequence.
- [x] Obtain approval for the complete sequence: copy the 386 listed photo-related
  files to pilot evidence and verify their identities, delete `local/reviews/`,
  then delete this task's temporary recovery directory after post-deletion checks.
  Preserve canonical Git/source, other worktrees, originals, library, references,
  model caches and other pilot data. Recheck writers and source identities first;
  stop on changed input, destination collisions or failed preservation.
- [x] Verify both authorized removals. Rechecked all 386 copied photo files and
  61 receipt hashes, 2,152 preexisting photo-file metadata entries and 149 canonical
  file records after review-tree deletion. All matched. The user-approved temporary
  recovery folder was then deleted; both removal commands exited 0. No unchanged
  successful runtime tests were repeated.

The completed photo preservation includes the earlier **unaccepted dragonfly
rev-007** project, its hash record, 40 trial views and 13 source-search artifacts.
It does not restore or replace the missing accepted rev-008 project. Bytes were preserved
without importing, migrating, opening or promoting that earlier project.

**Sources:** [Git bundle limitations](https://git-scm.com/docs/git-bundle) distinguish
refs/commits from local index/worktree state. The installed native `bsdtar` help and
[libarchive's manual](https://github.com/libarchive/libarchive/blob/master/tar/bsdtar.1)
explain preservation flags; the recorded nonzero exit limits the actual result.

## Photo-test and pilot retirement — completed 2026-10-28

After reviewing the exact inventory, the user approved “Delete both, including
listed photos.” Removed `local/photo-tests/` and `local/pilots/`: 2,242 approved
files / 5,202,498,796 logical bytes, including two DNG originals, both legacy
accepted rev-007 project directories and the 386 photo-related files/61 acceptance records
previously preserved beside the pilots. No replacement backup was created.
This explicit decision supersedes the earlier retention requirements for these
specific roots; other storage is outside scope.

Preflight matched all 2,531 entries and found no open target handles. Pilot removal
first stopped when a new standard `.DS_Store` appeared. Its generated metadata was
classified; all remaining photo files still matched the approval inventory. The
same approved directory was temporarily renamed and removed, including that
metadata; the temporary directory was also removed. Both targets are absent.

Post-deletion checks verified all 450 library/reference/configuration entries,
including 386 regular-file hashes, and 149 canonical file records before the two
intentional documentation status updates. Git HEAD/index remained unchanged;
root-library spider acceptance is still rev-006. No application code, model cache,
library format or photographic acceptance was changed. Historical pilot-specific
retention statements and launcher results above describe now-retired checkpoints.
