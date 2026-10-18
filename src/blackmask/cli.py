"""Bounded offline photo-project commands; no viewer or downloads."""

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
from .project import ProjectError, accept_development, create_project, read_project


def doctor(path: Path) -> dict[str, Any]:
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
        "models": "not installed or evaluated",
        "backend": "no inference performed",
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
    accepted.add_argument("--development", required=True, action="store_true")
    accepted.add_argument("--master-id", required=True, help="Identity of the master you inspected")
    checked = commands.add_parser("doctor", help="Report local preflight without downloading")
    checked.add_argument("--project", type=Path, default=Path.cwd())
    arguments = parser.parse_args()
    try:
        if arguments.command == "open":
            if arguments.source is not None:
                development = {
                    "assume_srgb": arguments.assume_srgb,
                    "white_balance": arguments.white_balance,
                }
                create_project(arguments.source, arguments.project, development)
            result = read_project(arguments.project)
        elif arguments.command == "accept":
            result = accept_development(arguments.project, arguments.master_id)
        else:
            result = doctor(arguments.project)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except (ProjectError, IngestError, OSError) as error:
        print(f"blackmask: {error}", file=sys.stderr)
        return 1
