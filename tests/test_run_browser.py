"""Runner path/preflight contracts; subprocess doubles never launch a browser."""

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest
import run_browser


def selected_packages(path):
    package = path / "playwright"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (package / "sync_api.py").write_text("def sync_playwright(): pass\n")
    implementation = package / "_impl"
    implementation.mkdir()
    (implementation / "__init__.py").write_text("")
    (implementation / "_driver.py").write_text(
        "import os\n"
        "from pathlib import Path\n"
        "def compute_driver_executable():\n"
        "    root = Path(__file__).parents[1] / 'driver'\n"
        "    return os.getenv('PLAYWRIGHT_NODEJS_PATH', root / 'node'), root / 'package/cli.js'\n"
    )
    driver = package / "driver"
    (driver / "package").mkdir(parents=True)
    (driver / "node").write_text("synthetic driver; never executed")
    (driver / "node").chmod(0o700)
    (driver / "package/cli.js").write_text("synthetic driver; never executed")
    return path


@pytest.fixture
def browser_process(monkeypatch):
    real_popen = subprocess.Popen
    launches = []
    waits = []
    signals = []
    timed_out = []

    class Process:
        pid = 43210

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def wait(self, timeout):
            waits.append(timeout)
            if timed_out and len(waits) <= 2:
                raise subprocess.TimeoutExpired("synthetic browser", timeout)
            return 0

    def launch(command, **kwargs):
        if "-I" in command:
            return real_popen(command, **kwargs)
        launches.append((command, kwargs))
        return Process()

    monkeypatch.setattr(run_browser.subprocess, "Popen", launch)
    monkeypatch.setattr(run_browser.os, "killpg", lambda pid, sig: signals.append((pid, sig)))
    monkeypatch.setattr(run_browser.sys, "platform", "darwin")
    return launches, waits, signals, timed_out


def invoke(monkeypatch, *arguments):
    monkeypatch.setattr(sys, "argv", ["run_browser.py", *map(str, arguments)])
    return run_browser.main()


def test_explicit_paths_and_isolation_contract(tmp_path, monkeypatch, browser_process, capsys):
    packages = selected_packages(tmp_path / "selected packages")
    evidence = tmp_path / "evidence with spaces"
    monkeypatch.setenv("BLACKMASK_SAM_CACHE", "/unselected/model")
    monkeypatch.setenv("PYTHONPATH", "/unselected/packages")
    monkeypatch.setenv("PLAYWRIGHT_NODEJS_PATH", sys.executable)
    assert invoke(monkeypatch, "--packages", packages, "--evidence-root", evidence) == 0
    launches, waits, _, _ = browser_process
    assert len(launches) == 1
    command, options = launches[0]
    workspace = next(evidence.iterdir())
    receipt = json.loads((workspace / "command.json").read_text())
    assert receipt["package_path"] == str(packages)
    assert receipt["cwd"] == str(Path(run_browser.__file__).resolve().parents[1])
    assert command[0] == "/usr/bin/sandbox-exec"
    policy = command[command.index("-p") + 1]
    assert "(deny file-write*)" in policy
    assert "(deny network-outbound)" in policy
    assert '(remote ip "localhost:*")' in policy
    assert f"--basetemp={workspace / 'pytest'}" in command
    assert options["start_new_session"] is True
    environment = options["env"]
    assert environment["PYTHONPATH"].split(os.pathsep)[0] == str(packages)
    assert "BLACKMASK_SAM_CACHE" not in environment
    assert "PLAYWRIGHT_NODEJS_PATH" not in environment
    assert environment["HOME"] == str(workspace / "home")
    assert environment["HF_HUB_OFFLINE"] == "1"
    assert environment["TRANSFORMERS_OFFLINE"] == "1"
    assert waits == [1800]
    assert json.loads((workspace / "exit.json").read_text()) == {"exit_code": 0}
    assert str(workspace) in capsys.readouterr().out


def test_default_evidence_is_fresh_temporary_storage(tmp_path, monkeypatch, browser_process):
    packages = selected_packages(tmp_path / "packages")
    monkeypatch.setattr(run_browser.tempfile, "tempdir", str(tmp_path))
    for _ in range(2):
        assert invoke(monkeypatch, "--packages", packages) == 0
    roots = [Path(options["env"]["HOME"]).parent for _, options in browser_process[0]]
    assert roots[0] != roots[1]
    assert all(root.parent == tmp_path and (root / "exit.json").is_file() for root in roots)


@pytest.mark.parametrize(
    "incomplete", ["absent", "empty", "import", "driver", "node", "ambient-driver"]
)
def test_invalid_selected_setup_precedes_evidence_and_launch(
    tmp_path, monkeypatch, browser_process, incomplete
):
    packages = tmp_path / "selected packages"
    if incomplete == "empty":
        (packages / "playwright").mkdir(parents=True)
    elif incomplete != "absent":
        selected_packages(packages)
        if incomplete == "import":
            (packages / "playwright/sync_api.py").write_text("import missing_selected_dependency\n")
        elif incomplete == "driver":
            (packages / "playwright/driver/package/cli.js").unlink()
        elif incomplete == "node":
            (packages / "playwright/driver/node").chmod(0o600)
        else:
            (packages / "playwright/driver/node").unlink()
            monkeypatch.setenv("PLAYWRIGHT_NODEJS_PATH", sys.executable)
    ambient = selected_packages(tmp_path / "ambient packages")
    monkeypatch.setenv("PYTHONPATH", str(ambient))
    evidence = tmp_path / "must not exist"
    monkeypatch.setattr(
        run_browser.tempfile, "mkdtemp", lambda **kwargs: pytest.fail("Created temporary storage")
    )
    with pytest.raises(SystemExit, match="--packages.*requirements-browser-macos-arm64.lock"):
        invoke(monkeypatch, "--packages", packages, "--evidence-root", evidence)
    assert not evidence.exists()
    assert browser_process[0] == []


def test_packages_argument_required(monkeypatch, browser_process):
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch)
    assert error.value.code == 2
    assert browser_process[0] == []


def test_timeout_records_failure_and_signals_owned_group(tmp_path, monkeypatch, browser_process):
    packages = selected_packages(tmp_path / "packages")
    evidence = tmp_path / "evidence"
    browser_process[3].append(True)
    assert invoke(monkeypatch, "--packages", packages, "--evidence-root", evidence) == 124
    assert browser_process[1] == [1800, 10, 10]
    assert browser_process[2] == [(43210, signal.SIGINT), (43210, signal.SIGKILL)]
    workspace = next(evidence.iterdir())
    assert json.loads((workspace / "exit.json").read_text()) == {"exit_code": 124}
    assert "timed out" in (workspace / "pytest.log").read_text()
