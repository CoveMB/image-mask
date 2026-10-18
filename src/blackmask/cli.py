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
from .review import review_project


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
        else "pass --model-cache to verify pinned SAM assets",
        "auto_device": "cpu",
        "backend": "CPU float32 baseline; explicit MPS is diagnostic for SAM and ViTMatte",
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="blackmask")
    commands = parser.add_subparsers(dest="command", required=True)
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
        "accept", help="Record explicit human development, trimap or final-photo approval"
    )
    accepted.add_argument("project", type=Path)
    choice = accepted.add_mutually_exclusive_group(required=True)
    choice.add_argument("--development", action="store_true")
    choice.add_argument("--revision")
    accepted.add_argument(
        "--trimap",
        action="store_true",
        help="Review authoritative prepared trimap; requires revision/master/digest",
    )
    accepted.add_argument("--inputs-digest")
    accepted.add_argument("--master-id", help="Identity of the master you inspected")
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
        "--crops", type=Path, help="JSON list of native half-open crop rectangles"
    )
    exported = commands.add_parser(
        "export", help="Export accepted RGB16 black/alpha16 and labelled viewing PNGs"
    )
    exported.add_argument("project", type=Path)
    exported.add_argument("--revision")
    exported.add_argument("--draft", action="store_true")
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
    arguments = parser.parse_args()
    try:
        if arguments.command == "open":
            if arguments.source is not None:
                development = {
                    "assume_srgb": arguments.assume_srgb,
                    "white_balance": arguments.white_balance,
                }
                create_project(arguments.source, arguments.project, development)
            result = dict(
                read_project(arguments.project), inputs_digest=draft_digest(arguments.project)
            )
            if not arguments.headless:
                from .viewer import open_viewer

                open_viewer(arguments.project, arguments.model_cache, arguments.sam_cache)
                return 0
        elif arguments.command == "accept":
            if arguments.trimap:
                if (
                    arguments.revision is None
                    or arguments.master_id is None
                    or arguments.inputs_digest is None
                ):
                    raise ProjectError(
                        "Trimap approval requires --revision, --master-id and --inputs-digest"
                    )
                result = accept_trimap(
                    arguments.project,
                    arguments.revision,
                    arguments.master_id,
                    arguments.inputs_digest,
                )
            elif arguments.revision is not None:
                if arguments.inputs_digest is not None or arguments.master_id is not None:
                    raise ProjectError(
                        "Final-photo acceptance uses --revision; trimap identity flags require --trimap"
                    )
                result = accept_revision(arguments.project, arguments.revision)
            else:
                if arguments.master_id is None or arguments.inputs_digest is not None:
                    raise ProjectError("Development approval requires the inspected --master-id")
                result = accept_development(arguments.project, arguments.master_id)
        elif arguments.command == "setup-model":
            result = (
                setup_sam(arguments.model_cache)
                if arguments.model == "sam"
                else setup_vitmatte(arguments.model_cache)
            )
        elif arguments.command == "review":
            crops = json.loads(arguments.crops.read_bytes()) if arguments.crops else None
            result = review_project(arguments.project, revision=arguments.revision, crops=crops)
        elif arguments.command == "export":
            result = export_project(
                arguments.project, revision=arguments.revision, draft=arguments.draft
            )
        elif arguments.command == "restore":
            from .operations import restore_revision

            result = restore_revision(
                arguments.project, arguments.revision, replace_drafts=arguments.replace_drafts
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
                model_cache=arguments.model_cache,
                source=arguments.source,
            )
        elif arguments.command == "status":
            result = operation_status(arguments.project)
        elif arguments.command == "run":
            result = apply_operation(
                arguments.project,
                json.loads(arguments.request.read_bytes()),
                model_cache=arguments.model_cache,
                request_file=arguments.request,
            )
        else:
            result = doctor(arguments.project, arguments.model_cache, arguments.model)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except (ProjectError, IngestError, OSError, ValueError, TypeError) as error:
        print(f"blackmask: {error}", file=sys.stderr)
        return 1
