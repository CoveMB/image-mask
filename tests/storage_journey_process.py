"""Process and filesystem boundaries for the existing storage acceptance journey."""

import fcntl
import json
import os
import select
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace


def install_guard(workspace, *, read_roots=None):
    """Audit Python filesystem effects; not an OS sandbox for native extensions."""
    workspace = workspace.resolve()
    reads = None if read_roots is None else tuple(path.resolve() for path in read_roots)
    enabled = [True]
    observed = set()
    descriptor_context = threading.local()
    original_open = os.open

    def relative_path(path, descriptor=None):
        if isinstance(path, int) or path is None or Path(os.fsdecode(path)).is_absolute():
            return path
        if descriptor is not None and descriptor >= 0:
            if sys.platform == "darwin":
                directory = os.fsdecode(fcntl.fcntl(descriptor, 50, bytes(1024)).split(b"\0", 1)[0])
            else:
                directory = os.readlink(f"/proc/self/fd/{descriptor}")
            return Path(directory) / os.fsdecode(path)
        return path

    def guarded_open(path, flags, mode=0o777, *, dir_fd=None):
        previous = getattr(descriptor_context, "directory", None)
        descriptor_context.directory = dir_fd
        try:
            return original_open(path, flags, mode, dir_fd=dir_fd)
        finally:
            descriptor_context.directory = previous

    os.open = guarded_open

    def check(path, writing):
        if isinstance(path, int) or path is None:
            return
        resolved = Path(os.fsdecode(path)).resolve()
        if resolved == Path("/dev/null"):
            return
        if writing and not resolved.is_relative_to(workspace):
            raise PermissionError(f"Journey write outside workspace: {resolved}")
        if not writing and reads is not None:
            if not any(resolved.is_relative_to(root) for root in reads):
                raise PermissionError(f"Journey read outside delivered assets/runtime: {resolved}")
            observed.add(str(resolved))

    def audit(event, arguments):
        if not enabled[0]:
            return
        if event == "open":
            path, _mode, flags = arguments
            writing = bool(
                flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
            )
            path = relative_path(path, getattr(descriptor_context, "directory", None))
            # Canonical saved-asset readers walk ancestor directory descriptors.
            if not writing and flags & os.O_DIRECTORY:
                return
            check(path, writing)
        elif event in {"os.rename", "os.link", "os.symlink"}:
            for index, path in enumerate(arguments[:2]):
                descriptor = arguments[index + 2] if event != "os.symlink" else None
                check(relative_path(path, descriptor), True)
        elif event in {"os.mkdir", "os.remove", "os.rmdir", "os.chmod", "os.truncate"}:
            descriptor = (
                arguments[-1]
                if event in {"os.mkdir", "os.remove", "os.rmdir", "os.chmod"}
                else None
            )
            check(relative_path(arguments[0], descriptor), True)
        elif event in {"os.listdir", "os.scandir"}:
            check(arguments[0], False)
        elif event in {"socket.connect", "socket.bind"}:
            address = arguments[1]
            if reads is not None or not isinstance(address, tuple) or address[0] != "127.0.0.1":
                raise PermissionError("Journey network access denied")

    sys.addaudithook(audit)

    def release():
        enabled[0] = False
        os.open = original_open

    return release, observed


def filesystem_entries(root):
    """Include directories and aliases omitted by the existing byte inventory."""
    result = {}
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        relative = str(path.relative_to(root))
        if path.is_symlink():
            result[relative] = ("symlink", os.readlink(path))
        elif path.is_dir():
            result[relative] = ("directory",)
        else:
            result[relative] = ("file", info.st_nlink)
    return result


def process_environment(workspace):
    """Bind every child to this checkout and test-owned writable runtime paths."""
    code_root = Path(__file__).resolve().parents[1]
    return dict(
        os.environ,
        PYTHONPATH=os.pathsep.join((str(code_root / "src"), str(code_root / "tests"))),
        PYTHONDONTWRITEBYTECODE="1",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        HOME=str(workspace / "home"),
        XDG_CACHE_HOME=str(workspace / "home/cache"),
        TMPDIR=str(workspace),
    )


@contextmanager
def running_process(project, config_file, workspace):
    """Run the shipped server in a new interpreter; replace inference only."""
    with (workspace / "viewer-process.stderr").open("ab") as errors:
        child = subprocess.Popen(
            [
                sys.executable,
                "-B",
                str(Path(__file__).resolve()),
                str(project),
                str(config_file),
                str(workspace),
            ],
            cwd=workspace,
            env=process_environment(workspace),
            stdout=subprocess.PIPE,
            stderr=errors,
            text=True,
        )
        try:
            assert select.select([child.stdout], [], [], 30)[0], "Viewer startup timed out"
            line = child.stdout.readline()
            assert line, (workspace / "viewer-process.stderr").read_text()
            server = SimpleNamespace(**json.loads(line), process=child)
            yield server
        finally:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=10)
            child.stdout.close()


def perform(server, action, **extra):
    from test_viewer import http

    status, body, _ = http(server)
    assert status == 200, body
    state = json.loads(body)
    data = {
        "action": action,
        "developed_id": state["developed_id"],
        "base_revision": state["working_revision"],
        "inputs_digest": state["inputs_digest"],
        "authoring_digest": state["authoring_digest"],
    }
    data.update(extra)
    status, body, _ = http(server, "/api/action", "POST", data)
    assert status == 202, body
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        status, body, _ = http(server)
        assert status == 200, body
        state = json.loads(body)
        if not state["action"]["running"]:
            assert state["action"]["error"] is None, state["action"]
            return state["action"]["result"]
        time.sleep(0.02)
    raise AssertionError("Viewer action timed out")


if __name__ == "__main__":
    from test_library_storage_journey import CachedPrediction

    from blackmask import library, operations
    from blackmask.viewer import ReviewServer

    project, config_file, workspace = map(Path, sys.argv[1:])
    install_guard(workspace)
    operations.VitMatteSession = CachedPrediction
    config = library.load_storage_config(config_file)
    with ReviewServer(
        project, config.vitmatte_cache, config.sam_cache, storage_config=config
    ) as server:
        print(
            json.dumps(
                {
                    "server_port": server.server_port,
                    "token": server.token,
                    "origin": server.origin,
                    "pid": os.getpid(),
                }
            ),
            flush=True,
        )
        server.serve_forever()
