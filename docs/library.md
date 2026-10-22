# Local photo library

The optional library owns each imported original once, alongside its editable
schema-2 project. Standalone projects remain supported. Processing stays local;
model setup is separate and never runs during library initialization or import.

Copy `config/storage.example.toml` to the ignored `config/storage.local.toml` and
choose a destination in `[storage]`. The example uses `../local`. Relative paths
are resolved against the selected configuration file's parent, so the same explicit
file selects the same library from another working directory or code checkout.
There is no automatic config search or fallback destination. Changing the setting
does not move an existing library or its pending imports.

Use the installed `blackmask` command, or `.venv/bin/blackmask` from the repository:

| Action | Command arguments |
| --- | --- |
| Create missing library folders | `--config FILE library-init` |
| Import one Inbox capture | `--config FILE import SOURCE --subject LABEL` |
| Include selected same-stem sidecars | Add one `--sidecar FILE` per file |
| Supply a known capture date | Add `--capture-date YYYY-MM-DD` |
| Resume an interrupted import | `--config FILE import-resume PENDING/import.json` |
| Open the returned project | `--config FILE open --project PROJECT` |
| Read existing project status | `--config FILE status PROJECT` |
| Repair the latest Result gallery image | `--config FILE preview repair PROJECT` |

Initialize first, then place the selected regular capture and optional sidecars
directly inside `Inbox`. No neighboring files are selected automatically. Sidecars
are preserved as provenance; their third-party edits are not applied. Existing
[source format, profile and development rules](../README.md#setup-and-quick-start)
apply, including explicit `--assume-srgb` or `--white-balance daylight` when needed.
Source-development review is optional; import does not accept a final photograph.

The library contains `Inbox`, `Photos`, `Results Preview` and `Comparisons`.
An imported folder is named `P<12-source-hash-characters>_<date-or-undated>_<subject>`.
Use one readable subject component, with no surrounding whitespace, path separators
or control characters. Unicode and internal spaces are supported. The folder name
is frozen at import; the camera filename stays unchanged. Its `original/` holds the
capture and declared sidecars; `project/` holds the editable project. Import creates
no Result, gallery image or acceptance event. The comparison folder can remain empty.
Complete native generation maintains one `<frozen-folder-name>.jpg` with a
Draft/Accepted footer outside the photograph. It follows the latest generated Result
after restoring older work. This reduced lossy viewing copy never replaces editable
layers or native exports.

Use the same explicit config for imported-project run, resume, acceptance, restore,
export and viewer actions. Read-only status/open without config reports missing
context. Configured reopen or explicit repair rebuilds pending output from saved
assets without models or the original. Polling never repairs. Native completion
survives gallery failure with `preview_pending`; resolve the reported cause and
retry repair. Unknown collisions and failed temporaries remain preserved.

New subject proposals must leave room for `.jpg` in the actual gallery parent's
filename-byte limit, including the fixed photo/date prefix. Unicode bytes count.
This check precedes duplicate lookup. Existing longer names and pending imports
remain usable: generation reports `name_too_long` with required/available bytes,
repair remains pending and acceptance changes are blocked. No alias or migration
is available. See the [gallery contract](file-contract.md#current-result-gallery).

Complete source hashes determine ownership. Reimporting identical bytes under a
different name, subject or development selection returns the existing project;
the extra Inbox capture and sidecars remain untouched. The JSON response reports
`input_preserved`. A matching interrupted import returns `status: "pending"` and
its exact recovery path. Resume that record explicitly rather than starting another
photo. A short-ID collision or malformed ownership record stops visibly.

Imports share one nonblocking library lock. A competing importer receives a busy
error and can retry; processing an existing photo uses its separate project lock.
Paths containing managed symlinks, dangling links, files in directory positions or
permission conflicts are rejected. New library/import directories are private
(0700), and new generated import/project files use 0600 even with a restrictive
umask. Existing permissions and moved original/sidecar modes are preserved.
Loading settings and reading status
create nothing. Selected paths must be valid before an import creates folders or
a lock file. Cross-device moves are refused before the first original moves; there
is no automatic copy/delete fallback.

The private `Inbox/.imports/` records the exact hashes and relative locations needed
after interruption. Preparation validates a complete developed project before any
original move. Resume checks actual Inbox, staging and final locations; it refuses
contradictory or changed files. Failed preparation attempts and uncertain remnants
remain preserved. Do not delete these records, move their contents by hand or
remove a lock file to recover. A failure after publication may leave a complete
photo with uncertain directory durability; resume checks and reports actual saved
state rather than promising rollback. Retain the original configuration to resume
an old library. See the normative [file contract](file-contract.md#configured-library-and-original-ownership).

Optional `[models] sam_cache` and `vitmatte_cache` select existing pinned native
directories shared by all photos. Explicit CLI flags take precedence; config
precedes `BLACKMASK_SAM_CACHE` and `BLACKMASK_VITMATTE_CACHE`. `open` uses separate
SAM and ViTMatte paths, `run` selects SAM for preparation and ViTMatte for matte or
repair, and `resume` uses ViTMatte. Missing or invalid pinned assets remain errors;
initialization and import never copy or download models. Preserve model versions
needed for offline work. Saved-layer replay still needs no models or original path.

Keep the library and local config ignored or outside the repository. The root
`library/`, root `local/` and `config/storage.local.toml` are ignored by this
repository; another in-repository destination needs its own ignore rule before use.
Only the portable example is distributed. Ignored originals and recovery records
are not disposable and are not backed up by Git. Back up the whole library,
configuration and necessary model versions independently. No automatic migration,
watcher, catalog or cleanup runs.
