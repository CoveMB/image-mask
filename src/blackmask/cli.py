"""Offline project/preparation commands; downloads only through explicit setup-model."""

import argparse
import json
import platform
import shutil
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Any

import rawpy

from .export import export_project
from .ingest import IngestError
from .library import (
    ensure_library,
    import_photo,
    load_storage_config,
    resume_import,
    validate_library_project,
)
from .models import setup_sam, setup_vitmatte, verify_sam, verify_vitmatte
from .operations import (
    accept_revision,
    accept_trimap,
    apply_operation,
    draft_digest,
    operation_status,
    resume_operation,
)
from .project import ProjectError, accept_development, create_project, read_project
from .review import review_cycle, review_project


def doctor(path: Path, model_cache: Path | None = None, model: str = "sam") -> dict[str, Any]:
    return {
        "python": platform.python_version(),
        "machine": platform.machine(),
        "os": platform.platform(),
        "native_arm64_python312": platform.machine() == "arm64" and sys.version_info[:2] == (3, 12),
        "packages": {
            name: version(name) for name in ("numpy", "Pillow", "tifffile", "rawpy", "tomli-w")
        },
        "libraw": list(rawpy.libraw_version),
        "libraw_flags": rawpy.flags,
        "free_bytes": shutil.disk_usage(path).free,
        "reserve_bytes": 10 * 1024**3,
        "models": (verify_sam(model_cache) if model == "sam" else verify_vitmatte(model_cache))
        if model_cache is not None
        else f"pass --model-cache to verify pinned {'SAM' if model == 'sam' else 'ViTMatte'} assets",
        "auto_device": "cpu",
        "backend": "CPU float32 baseline; explicit MPS is diagnostic for SAM and ViTMatte",
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="blackmask")
    parser.add_argument("--config", type=Path, help="Explicit local storage TOML; no discovery")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("library-init", help="Safely create the configured library folders")
    imported = commands.add_parser(
        "import", help="Move a selected Inbox original and declared sidecars"
    )
    imported.add_argument("source", type=Path)
    imported.add_argument("--subject", required=True)
    imported.add_argument("--capture-date")
    imported.add_argument("--sidecar", type=Path, action="append", default=[])
    imported.add_argument("--assume-srgb", action="store_true")
    imported.add_argument("--white-balance", choices=("camera", "daylight"), default="camera")
    imported_resume = commands.add_parser("import-resume", help="Resume one exact pending import")
    imported_resume.add_argument("pending", type=Path)
    opened = commands.add_parser(
        "open", help="Create/reopen a project and open its offline review window"
    )
    opened.add_argument("source", nargs="?", type=Path)
    opened.add_argument("--project", required=True, type=Path)
    opened.add_argument(
        "--headless",
        action="store_true",
        help="Validate/create and return JSON without a server/browser",
    )
    opened.add_argument(
        "--sam-cache", type=Path, help="Explicit local pinned SAM cache; no downloads"
    )
    opened.add_argument(
        "--model-cache", type=Path, help="Explicit local pinned model cache; no downloads"
    )
    opened.add_argument("--assume-srgb", action="store_true")
    opened.add_argument("--white-balance", choices=("camera", "daylight"), default="camera")
    accepted = commands.add_parser(
        "accept", help="Record trimap/final-photo approval or optional legacy development review"
    )
    accepted.add_argument("project", type=Path)
    choice = accepted.add_mutually_exclusive_group(required=True)
    choice.add_argument("--development", action="store_true")
    choice.add_argument("--revision")
    accepted.add_argument(
        "--trimap",
        action="store_true",
        help="Optionally review authoritative prepared trimap; requires revision/master/digest",
    )
    accepted.add_argument("--inputs-digest")
    accepted.add_argument("--developed-id", help="Identity of the master you inspected")
    checked = commands.add_parser("doctor", help="Report local preflight without downloading")
    checked.add_argument("--project", type=Path, default=Path.cwd())
    checked.add_argument("--model-cache", type=Path)
    checked.add_argument("--model", choices=("sam", "vitmatte"), default="sam")
    setup = commands.add_parser(
        "setup-model", help="Explicitly download hash-pinned public model assets"
    )
    setup.add_argument("--model-cache", type=Path, required=True)
    setup.add_argument("--model", choices=("sam", "vitmatte"), default="sam")
    running = commands.add_parser(
        "run", help="Prepare guidance, run native matte or apply scoped repair from a typed request"
    )
    running.add_argument("project", type=Path)
    running.add_argument("--request", type=Path, required=True)
    running.add_argument("--model-cache", type=Path)
    reviewed = commands.add_parser(
        "review", help="Export same-native-crop RGB8 source/result/alpha viewing assets"
    )
    reviewed.add_argument("project", type=Path)
    reviewed.add_argument("--revision")
    reviewed.add_argument(
        "--cycle-request",
        type=Path,
        help="Explicit assisted cycle start/assessment/stop/status JSON",
    )
    reviewed.add_argument(
        "--crops", type=Path, help="JSON list of native half-open crop rectangles"
    )
    exported = commands.add_parser(
        "export", help="Export accepted RGB16 black/alpha16 and labelled viewing PNGs"
    )
    exported.add_argument("project", type=Path)
    exported.add_argument("--revision")
    exported.add_argument("--draft", action="store_true")
    presentation = exported.add_mutually_exclusive_group()
    presentation.add_argument(
        "--margins",
        nargs=4,
        type=int,
        metavar=("LEFT", "RIGHT", "TOP", "BOTTOM"),
        help="Create a separate framed presentation using nonnegative native pixel margins",
    )
    presentation.add_argument(
        "--series-preset",
        type=Path,
        help="Create a fixed-size resized presentation from a portable series JSON preset",
    )
    exported.add_argument(
        "--framed-transparent",
        action="store_true",
        help="Include a reduced-precision straight RGBA8 view; requires --margins or --series-preset",
    )
    restored = commands.add_parser(
        "restore", help="Restore saved working inputs; retain acceptance"
    )
    restored.add_argument("project", type=Path)
    restored.add_argument("--revision", required=True)
    restored.add_argument(
        "--replace-drafts",
        action="store_true",
        help="Explicitly replace unsaved drafts; retain prior bytes in recovery",
    )
    replayed = commands.add_parser("replay", help="Verify saved repair alpha without models/cache")
    replayed.add_argument("project", type=Path)
    replayed.add_argument("--revision", required=True)
    resumed = commands.add_parser("resume", help="Resume verified interrupted matte/repair work")
    resumed.add_argument("project", type=Path)
    resumed.add_argument("--operation", required=True)
    resumed.add_argument("--model-cache", type=Path)
    resumed.add_argument(
        "--source", type=Path, help="Optional moved capture; must match recorded hash"
    )
    status = commands.add_parser("status", help="Read recovery status without waiting for a writer")
    status.add_argument("project", type=Path)
    preview = commands.add_parser(
        "preview", help="Explicitly repair the latest native Result gallery"
    )
    preview.add_argument("action", choices=("repair",))
    preview.add_argument("project", type=Path)
    arguments = parser.parse_args()
    try:
        config = load_storage_config(arguments.config) if arguments.config is not None else None
        if arguments.command in {
            "accept",
            "run",
            "resume",
            "restore",
            "review",
            "export",
            "preview",
        }:
            validate_library_project(arguments.project, config)
        result: dict[str, Any]
        if arguments.command in {"library-init", "import", "import-resume"}:
            if config is None:
                raise ProjectError("Library commands require an explicit --config FILE")
            if arguments.command == "library-init":
                ensure_library(config)
                result = {"destination": str(config.destination)}
            else:
                path = (
                    resume_import(config, arguments.pending)
                    if arguments.command == "import-resume"
                    else import_photo(
                        config,
                        arguments.source,
                        subject=arguments.subject,
                        capture_date=arguments.capture_date,
                        development={
                            "assume_srgb": arguments.assume_srgb,
                            "white_balance": arguments.white_balance,
                        },
                        sidecars=tuple(arguments.sidecar),
                    )
                )
                result = (
                    {"status": "pending", "pending": str(path), "input_preserved": True}
                    if path.name == "import.json"
                    else {"status": "ready", "project": str(path)}
                )
                if arguments.command == "import":
                    result["input_preserved"] = arguments.source.exists()
        elif arguments.command == "open":
            if arguments.source is not None:
                development = {
                    "assume_srgb": arguments.assume_srgb,
                    "white_balance": arguments.white_balance,
                }
                create_project(arguments.source, arguments.project, development)
            result = dict(
                read_project(arguments.project), inputs_digest=draft_digest(arguments.project)
            )
            from .previews import refresh_result_preview, result_preview_status

            result["preview"] = (
                refresh_result_preview(arguments.project, config)
                if config is not None and arguments.headless
                else result_preview_status(arguments.project, config)
            )
            result["preview_pending"] = result["preview"]["status"] == "pending"
            if not arguments.headless:
                from .viewer import open_viewer

                open_viewer(
                    arguments.project,
                    arguments.model_cache or (config.vitmatte_cache if config else None),
                    arguments.sam_cache or (config.sam_cache if config else None),
                    storage_config=config,
                )
                return 0
        elif arguments.command == "accept":
            if arguments.trimap:
                if (
                    arguments.revision is None
                    or arguments.developed_id is None
                    or arguments.inputs_digest is None
                ):
                    raise ProjectError(
                        "Trimap approval requires --revision, --developed-id and --inputs-digest"
                    )
                result = accept_trimap(
                    arguments.project,
                    arguments.revision,
                    arguments.developed_id,
                    arguments.inputs_digest,
                )
            elif arguments.revision is not None:
                if arguments.inputs_digest is not None or arguments.developed_id is not None:
                    raise ProjectError(
                        "Final-photo acceptance uses --revision; trimap identity flags require --trimap"
                    )
                result = accept_revision(
                    arguments.project, arguments.revision, storage_config=config
                )
            else:
                if arguments.developed_id is None or arguments.inputs_digest is not None:
                    raise ProjectError("Development approval requires the inspected --developed-id")
                result = accept_development(arguments.project, arguments.developed_id)
        elif arguments.command == "setup-model":
            result = (
                setup_sam(arguments.model_cache)
                if arguments.model == "sam"
                else setup_vitmatte(arguments.model_cache)
            )
        elif arguments.command == "review":
            crops = json.loads(arguments.crops.read_bytes()) if arguments.crops else None
            if arguments.cycle_request:
                if arguments.revision or arguments.crops:
                    raise ProjectError("Cycle requests cannot be combined with crop/revision flags")
                result = review_cycle(
                    arguments.project, json.loads(arguments.cycle_request.read_bytes())
                )
            else:
                result = review_project(arguments.project, revision=arguments.revision, crops=crops)
        elif arguments.command == "export":
            from .series_framing import read_series_preset_file

            result = export_project(
                arguments.project,
                revision=arguments.revision,
                draft=arguments.draft,
                framing=dict(
                    zip(
                        ("left_px", "right_px", "top_px", "bottom_px"),
                        arguments.margins,
                        strict=True,
                    )
                )
                if arguments.margins is not None
                else None,
                framed_transparent=arguments.framed_transparent,
                series=read_series_preset_file(arguments.series_preset).to_dict()
                if arguments.series_preset is not None
                else None,
            )
        elif arguments.command == "restore":
            from .operations import restore_revision

            result = restore_revision(
                arguments.project,
                arguments.revision,
                replace_drafts=arguments.replace_drafts,
                storage_config=config,
            )
        elif arguments.command == "replay":
            from .repair import replay_repair

            alpha = replay_repair(arguments.project, arguments.revision)
            result = {
                "revision": arguments.revision,
                "exact_replay": True,
                "dimensions_wh": [alpha.shape[1], alpha.shape[0]],
                "model_calls": 0,
            }
        elif arguments.command == "resume":
            result = resume_operation(
                arguments.project,
                arguments.operation,
                model_cache=arguments.model_cache or (config.vitmatte_cache if config else None),
                source=arguments.source,
                storage_config=config,
            )
        elif arguments.command == "status":
            result = operation_status(arguments.project, storage_config=config)
        elif arguments.command == "preview":
            from .previews import refresh_result_preview

            if config is None:
                raise ProjectError("Preview repair requires explicit --config FILE")
            result = refresh_result_preview(arguments.project, config)
        elif arguments.command == "run":
            request = json.loads(arguments.request.read_bytes())
            if not isinstance(request, dict):
                raise ProjectError("Operation request must be a JSON object")
            result = apply_operation(
                arguments.project,
                request,
                model_cache=arguments.model_cache
                or (
                    (
                        config.sam_cache
                        if request.get("kind") == "prepare"
                        else config.vitmatte_cache
                    )
                    if config
                    else None
                ),
                request_file=arguments.request,
                storage_config=config,
            )
        else:
            result = doctor(
                arguments.project,
                arguments.model_cache
                or (
                    (config.sam_cache if arguments.model == "sam" else config.vitmatte_cache)
                    if config
                    else None
                ),
                arguments.model,
            )
        print(json.dumps(result, indent=2, allow_nan=False))
        return 1 if arguments.command == "preview" and result["status"] == "pending" else 0
    except (ProjectError, IngestError, OSError, ValueError, TypeError) as error:
        print(f"blackmask: {error}", file=sys.stderr)
        return 1
