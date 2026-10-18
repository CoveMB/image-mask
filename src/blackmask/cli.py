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

from .ingest import IngestError
from .models import setup_sam, verify_sam
from .operations import accept_revision, apply_operation, draft_digest
from .project import ProjectError, accept_development, create_project, read_project


def doctor(path: Path, model_cache: Path | None = None) -> dict[str, Any]:
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
        "models": verify_sam(model_cache)
        if model_cache is not None
        else "pass --model-cache to verify pinned SAM assets",
        "auto_device": "cpu",
        "backend": "CPU float32 baseline; explicit MPS is diagnostic; ViTMatte unverified",
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="blackmask")
    commands = parser.add_subparsers(dest="command", required=True)
    opened = commands.add_parser("open", help="Create or validate/reopen a project (CLI only)")
    opened.add_argument("source", nargs="?", type=Path)
    opened.add_argument("--project", required=True, type=Path)
    opened.add_argument("--assume-srgb", action="store_true")
    opened.add_argument("--white-balance", choices=("camera", "daylight"), default="camera")
    accepted = commands.add_parser("accept", help="Record explicit human development approval")
    accepted.add_argument("project", type=Path)
    choice = accepted.add_mutually_exclusive_group(required=True)
    choice.add_argument("--development", action="store_true")
    choice.add_argument("--revision")
    accepted.add_argument("--master-id", help="Identity of the master you inspected")
    checked = commands.add_parser("doctor", help="Report local preflight without downloading")
    checked.add_argument("--project", type=Path, default=Path.cwd())
    checked.add_argument("--model-cache", type=Path)
    setup = commands.add_parser(
        "setup-model", help="Explicitly download hash-pinned public SAM assets"
    )
    setup.add_argument("--model-cache", type=Path, required=True)
    running = commands.add_parser("run", help="Prepare reviewable guidance from a typed request")
    running.add_argument("project", type=Path)
    running.add_argument("--request", type=Path, required=True)
    running.add_argument("--model-cache", type=Path)
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
        elif arguments.command == "accept":
            if arguments.revision is not None:
                accept_revision(arguments.project, arguments.revision)
                raise ProjectError("Final acceptance unavailable")
            if arguments.master_id is None:
                raise ProjectError("Development approval requires the inspected --master-id")
            result = accept_development(arguments.project, arguments.master_id)
        elif arguments.command == "setup-model":
            result = setup_sam(arguments.model_cache)
        elif arguments.command == "run":
            result = apply_operation(
                arguments.project,
                json.loads(arguments.request.read_bytes()),
                model_cache=arguments.model_cache,
                request_file=arguments.request,
            )
        else:
            result = doctor(arguments.project, arguments.model_cache)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except (ProjectError, IngestError, OSError, ValueError, TypeError) as error:
        print(f"blackmask: {error}", file=sys.stderr)
        return 1
