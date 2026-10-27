"""Run the explicit macOS browser lane with repository-owned tooling and evidence."""

import json
import os
import signal
import subprocess
import sys
import tempfile
from contextlib import suppress
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    if sys.platform != "darwin":
        raise SystemExit("Browser isolation currently requires macOS sandbox-exec")
    packages = root / "local/browser-runtime"
    if not (packages / "playwright").is_dir():
        raise SystemExit("Install requirements-browser-macos-arm64.lock as documented first")
    runs = root / "local/browser-runs"
    runs.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix="run-", dir=runs))
    # Chromium's macOS socket directory ignores TMPDIR; keep its path short.
    native_temp = Path(tempfile.mkdtemp(prefix="im-browser-", dir="/private/tmp"))
    (workspace / "home").mkdir()
    environment = dict(os.environ)
    for key in tuple(environment):
        if key.startswith("BLACKMASK_"):
            del environment[key]
    environment.update(
        BLACKMASK_BROWSER="1",
        PYTHONPATH=os.pathsep.join(str(path) for path in (packages, root / "src", root / "tests")),
        PYTHONDONTWRITEBYTECODE="1",
        HOME=str(workspace / "home"),
        XDG_CACHE_HOME=str(workspace / "cache"),
        TMPDIR=str(native_temp),
        MAC_CHROMIUM_TMPDIR=str(native_temp),
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
    )
    policy = (
        "(version 1)(allow default)(deny file-write*)"
        '(allow file-write* (subpath (param "workspace"))'
        ' (subpath (param "native_temp")) (literal "/dev/null"))'
        "(deny network-outbound)"
        '(allow network-outbound (remote ip "localhost:*"))'
    )
    timeout_seconds = 1800
    command = [
        "/usr/bin/sandbox-exec",
        "-D",
        f"workspace={workspace}",
        "-D",
        f"native_temp={native_temp}",
        "-p",
        policy,
        sys.executable,
        "-B",
        "-m",
        "pytest",
        "-q",
        "-ra",
        "-p",
        "no:cacheprovider",
        f"--basetemp={workspace / 'pytest'}",
        str(root / "tests/test_lifecycle_browser.py"),
    ]
    (workspace / "command.json").write_text(
        json.dumps(
            {
                "argv": command,
                "cwd": str(root),
                "python": sys.executable,
                "native_temp": str(native_temp),
                "package_path": str(packages),
                "timeout_seconds": timeout_seconds,
            },
            indent=2,
        )
    )
    print(f"Browser evidence: {workspace}", flush=True)
    with (
        (workspace / "pytest.log").open("w") as log,
        subprocess.Popen(
            command,
            cwd=root,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        ) as process,
    ):
        try:
            exit_code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            exit_code = 124
            log.write(f"\nBrowser lane timed out after {timeout_seconds} s\n")
            log.flush()
            # Let pytest and the browser driver close their children before
            # terminating any remaining members of this test-owned process group.
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGINT)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)
    (workspace / "exit.json").write_text(json.dumps({"exit_code": exit_code}))
    print((workspace / "pytest.log").read_text(), end="")
    print(f"Exit {exit_code}; logs and test-owned data retained in {workspace}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
