# Image Mask

A planned local workflow for turning one photograph into a black-background
image while preserving photographed detail. It combines editable masks, scoped
repairs and optional reversible color cleanup and inward shading. Photographic
quality takes priority over reducing recurring effort.

The intended workflow uses a native macOS/Apple Silicon Python engine, a small
localhost review window and optional Codex assistance. After explicit setup, the
complete manual workflow must remain usable without an assistant, credits or
internet access.

## Current status

This repository contains the specification, reviewed incremental plan and
experimental reference material. The application has not been implemented;
`blackmask` commands and test commands in the planning documents are proposed
interfaces, not a working quick start.

There is no verified dependency lock, installation procedure or model/backend
validation yet. `.python-version` declares the planned Python 3.12 baseline; it
does not install Python or establish compatibility. Packaging, dependency pins,
tests and CI should arrive with their approved implementation scope.

## Start here

| Document | Purpose |
| --- | --- |
| [Version 4 specification](single-photo-black-background-implementation-plan-v4-2026-10-11.txt) | Product scope, image contracts and acceptance criteria |
| [Incremental plan](docs/incremental-plans/single-photo-black-background-qa/plan.md) | Current delivery sequence, dependencies and approval gates |
| [QA plan](docs/incremental-plans/single-photo-black-background-qa/qa-plan.md) | Acceptance checks, evidence owners and regular-use runbook |
| [Current handoff](docs/incremental-plans/single-photo-black-background-qa/handoff.md) | I01 executor preparation only |
| [Review and comparison record](docs/incremental-plans/single-photo-black-background-qa/reviews.md) | Independent reports, plan selection and evidence limits |
| [Repository guidance](AGENTS.md) | Engineering, preservation and assistant rules |
| [Reference overview](Photo-workflow-reference/README.txt) | Experimental archive contents and provenance limits |

The coordinated plan/QA/handoff created on 2026-10-18 is the current planning
set, selected after comparison through three independent review scopes. The
[earlier plan and its linked records](docs/incremental-plans/single-photo-black-background/plan.md)
remain unchanged comparison history. Planning review permits I01 preparation;
concrete implementation and verified-result approvals remain required.

The specification controls product requirements; the incremental plan controls
delivery. Older DOCX guides and reference scripts preserve historical work and
do not override them. Some planning notes describe a pre-Git baseline; inspect
the actual checkout before acting. Do not run or import the experimental
scripts unchanged: some process files at import and overwrite fixed outputs.

## Intended safeguards

- Preserve original capture bytes and accepted revisions; never synthesize
  missing detail, anatomy, hairs or web.
- Retain a lossless RGB16 sRGB TIFF master and separate grayscale16 masks.
  Label lower-precision viewing copies honestly.
- Bind guides and scoped repairs to the correct master and revision, preserving
  protected regions and partial transparency exactly.
- Keep color cleanup and shading separate, reversible and disabled by default.
- Require human development review and photographic acceptance. AI review is
  advisory, with at most two automatic repair attempts per requested cycle.

Exact requirements and release evidence remain in the specification and plan.

## Local data and repository hygiene

Keep private captures, working photo projects, model downloads, credentials and
local evaluation output outside this repository. If an in-repository location
is needed, use the ignored root `local/` directory. Nothing in that directory is
backed up by Git; arrange separate storage and never treat it as disposable
cache. Do not put private data in public examples or test fixtures.

`.gitignore` excludes local environments, caches, secrets and generated output
without broadly hiding reference images or future synthetic fixtures.
`.gitattributes` preserves frozen source/reference bytes while normalizing
authored text. `.editorconfig` supplies editing conventions and excludes those
historical snapshots from its formatting settings.

Existing tracked Finder metadata is preserved. Adding ignore rules does not
remove files already tracked by Git.

## Licensing

No licence for original project code has been selected. Third-party references,
model weights and upstream implementations retain their own terms; see
[model and licence provenance](Photo-workflow-reference/MODELS_AND_LICENSES.txt).
Checkpoint licence labels do not establish the licence of separate research
code or grant rights to photographs.
