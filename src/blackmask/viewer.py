"""One-project loopback review boundary; no filesystem URL routing or downloads."""

import base64
import hashlib
import io
import json
import re
import secrets
import threading
import tomllib
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from . import operations
from .export import export_project, saved_layers
from .guidance import coordinates
from .project import (
    ProjectError,
    _asset,
    _root,
    _validate_assets,
    _validation_scope,
    accept_development,
    digest,
    read_project,
    read_revision,
)
from .review import review_panels


class ReviewServer(ThreadingHTTPServer):
    """Ephemeral server scoped to one validated project and one launch capability."""

    daemon_threads = True
    block_on_close = False

    def __init__(
        self, project: Path, model_cache: Path | None = None, sam_cache: Path | None = None
    ):
        self.project = _root(project)
        read_project(self.project, validate_drafts=False)
        self.model_cache = model_cache
        self.sam_cache = sam_cache
        self.token = secrets.token_urlsafe(32)
        self.action_lock = threading.Lock()
        self.action: dict[str, Any] = {"running": False, "error": None, "result": None}
        super().__init__(("127.0.0.1", 0), ReviewHandler)
        self.origin = f"http://127.0.0.1:{self.server_port}"
        self.host = f"127.0.0.1:{self.server_port}"

    @_validation_scope()
    def snapshot(self) -> dict[str, Any]:
        state = operations.operation_status(self.project)
        master, _ = _validate_assets(self.project, state, validate_drafts=False)
        height, width = master.shape[:2]
        state.update(
            dimensions_wh=[width, height],
            source_url=f"/image/source/{state['master_id']}/0,0,{width},{height}",
        )
        state["action"] = dict(self.action)
        state["draft_error"] = None
        try:
            state["inputs_digest"] = operations.draft_digest(self.project)
            state["guides"] = json.loads(_asset(self.project, "guides.json").read_bytes())
            state["recipe"] = tomllib.loads(_asset(self.project, "recipe.toml").read_text())
            read_project(self.project)
        except (OSError, ValueError, TypeError) as error:
            state["draft_error"] = str(error)
        try:
            state["pending"] = operations.pending_guidance(self.project)
        except ProjectError as error:
            state["pending"] = None
            state["draft_error"] = str(error)
        state["authoring_digest"] = operations.guidance_draft_digest(self.project)
        revisions = []
        for path in sorted(_asset(self.project, "revisions").glob("rev-*")):
            if re.fullmatch(r"rev-[0-9]{3,}", path.name):
                manifest = read_revision(self.project, path.name, state["master_id"])
                revisions.append(
                    {
                        "revision": path.name,
                        "kind": manifest["kind"],
                        "final_acceptable": manifest["final_acceptable"],
                        "candidates": [
                            {k: c[k] for k in ("id", "index", "score", "selected", "group_id")}
                            for c in manifest.get("candidates", [])
                        ],
                        "scope_xyxy": manifest.get("scope_xyxy"),
                        "draft_digest": manifest.get("draft_digest"),
                        "color_cleanup": manifest.get(
                            "color_cleanup", {"enabled": False, "stale": False}
                        ),
                        "shading": manifest.get("shading", {"enabled": False, "stale": False}),
                        "tile_summary": {
                            k: manifest.get("model", {}).get(k)
                            for k in ("inferred_tiles", "reused_tiles")
                        },
                    }
                )
        state["revisions"] = revisions
        return state

    def start_action(self, data: Any) -> None:
        if not isinstance(data, dict):
            raise ProjectError("Action must be a JSON object")
        action = data.get("action")
        fields = {
            "save": {"groups", "actions"},
            "prepare": {"scope_xyxy"},
            "development": set(),
            "trimap": {"revision"},
            "accept": {"revision"},
            "matte": set(),
            "effects": {"scope_xyxy", "support_file", "candidate_comparison"},
            "repair": {"context_xyxy", "scope_xyxy", "reason", "merge_policy"},
            "restore": {"revision", "replace_drafts"},
            "resume": {"operation_id"},
            "export": {"revision", "draft"},
        }
        if action == "effects":
            optional = {"color_cleanup", "shading", "shading_protection_file", "opacity_only"}
            fields["effects"] |= set(data) & optional
        if action not in fields or set(data) != fields[action] | {
            "action",
            "authoring_digest",
            "master_id",
            "base_revision",
            "inputs_digest",
        }:
            raise ProjectError("Invalid action or structured fields")
        if not self.action_lock.acquire(blocking=False):
            raise ProjectError("Viewer busy: wait for the current action")
        self.action = {"running": True, "name": action, "error": None, "result": None}

        def run() -> None:
            try:
                self.action["result"] = self.execute(data)
            except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
                self.action["error"] = str(error)
            finally:
                self.action["running"] = False
                self.action_lock.release()

        threading.Thread(target=run, daemon=True).start()

    def execute(self, data: dict[str, Any]) -> dict[str, Any]:
        action = data["action"]
        # Canonical processing owners recheck identities while holding their writer lock.
        if action == "save":
            return operations.save_guidance_draft(
                self.project, data, data["groups"], data["actions"]
            )
        if action == "prepare":
            return operations.prepare_guidance_draft(
                self.project, data, data["scope_xyxy"], model_cache=self.sam_cache
            )
        state = read_project(self.project, validate_drafts=action != "restore")
        if (
            data["master_id"] != state["master_id"]
            or data["base_revision"] != state["working_revision"]
            or data["inputs_digest"] != operations.draft_digest(self.project)
            or data.get("authoring_digest") != operations.guidance_draft_digest(self.project)
        ):
            raise ProjectError("Stale viewer identity; reload current project")
        pending = (
            operations.pending_guidance(self.project)
            if action in {"trimap", "matte", "repair", "accept", "effects"}
            else None
        )
        if pending and pending["current"] and pending["actions"]:
            raise ProjectError("Saved pending guidance requires prepare and trimap review first")
        if action == "development":
            return accept_development(self.project, data["master_id"])
        if action == "trimap":
            return operations.accept_trimap(
                self.project, data["revision"], data["master_id"], data["inputs_digest"]
            )
        if action == "accept":
            return operations.accept_revision(self.project, data["revision"])
        if action == "restore":
            if type(data["replace_drafts"]) is not bool:
                raise ProjectError("replace_drafts must be a boolean")
            return operations.restore_revision(
                self.project,
                data["revision"],
                replace_drafts=data["replace_drafts"],
                expected_identity=data,
            )
        if action == "resume":
            return operations.resume_operation(
                self.project, data["operation_id"], model_cache=self.model_cache
            )
        if action == "export":
            if type(data["draft"]) is not bool:
                raise ProjectError("draft must be a boolean")
            return export_project(self.project, revision=data["revision"], draft=data["draft"])
        request = {
            "schema_version": 1,
            "kind": action,
            "master_id": data["master_id"],
            "base_revision": data["base_revision"],
            "inputs_digest": data["inputs_digest"],
        }
        if action == "effects":
            request.update(
                {
                    k: data[k]
                    for k in (
                        "scope_xyxy",
                        "support_file",
                        "color_cleanup",
                        "candidate_comparison",
                        "shading",
                        "shading_protection_file",
                        "opacity_only",
                    )
                    if k in data
                }
            )
        if action == "repair":
            request.update(
                {k: data[k] for k in ("context_xyxy", "scope_xyxy", "reason", "merge_policy")}
            )
            request["support_file"] = (
                f"revisions/{state['working_revision']}/supports/support16.png"
            )
        return operations.apply_operation(self.project, request, model_cache=self.model_cache)

    @_validation_scope()
    def image(self, path: str) -> bytes:
        state = read_project(self.project, validate_drafts=False)
        match = re.fullmatch(
            r"/image/(source|black|gray|white|alpha)/([a-f0-9]{64}|rev-[0-9]{3,})/([0-9]+,[0-9]+,[0-9]+,[0-9]+)(/base|/p(?:0|0.12|0.24))?",
            path,
        )
        if not match:
            raise FileNotFoundError("Unknown image identity")
        panel, identity, rectangle, base = match.groups()
        source, _ = _validate_assets(self.project, state, validate_drafts=False)
        height, width = source.shape[:2]
        x0, y0, x1, y1 = coordinates(
            [int(v) for v in rectangle.split(",")], width, height, box=True
        )
        if panel == "source":
            if identity != state["master_id"]:
                raise FileNotFoundError("Wrong master identity")
            pixels = np.rint(source[y0:y1, x0:x1].astype(np.float64) / 257).astype(np.uint8)
        else:
            current = (
                read_revision(self.project, state["working_revision"], state["master_id"])
                if state["working_revision"]
                else {}
            )
            from .effects import effects_stale, saved_shading

            stale = effects_stale(current)
            foreground, alpha, manifest = saved_layers(
                self.project,
                identity,
                state["master_id"],
                effects_off=bool(base == "/base" or stale),
            )
            weight, opacity = saved_shading(
                self.project, identity, alpha, manifest, effects_off=bool(base == "/base" or stale)
            )
            if base and base.startswith("/p") and weight is not None:
                opacity = float(base[2:])
            pixels = review_panels(
                source[y0:y1, x0:x1],
                foreground[y0:y1, x0:x1],
                alpha[y0:y1, x0:x1],
                None if weight is None else weight[y0:y1, x0:x1],
                opacity,
            )[panel]
        buffer = io.BytesIO()
        Image.fromarray(pixels).save(buffer, format="PNG")
        return buffer.getvalue()

    @_validation_scope()
    def mask(self, path: str) -> bytes:
        match = re.fullmatch(r"/mask/(rev-[0-9]{3,})/([A-Za-z0-9_-]+)", path)
        if not match:
            raise FileNotFoundError("Unknown mask identity")
        revision, label = match.groups()
        state = read_project(self.project, validate_drafts=False)
        manifest = read_revision(self.project, revision, state["master_id"])
        names = {
            "trimap": "trimap.png",
            "support": "supports/support16.png",
            "lock": "supports/protection.png",
            "membership": "selected_membership.png",
            "proposal": "trimap_proposal.png",
            "boundary": "proposal_boundary.png",
        }
        names.update({c["id"]: c["mask_file"] for c in manifest.get("candidates", [])})
        name = names.get(label)
        if name is None or name not in manifest["files"]:
            raise FileNotFoundError("Mask not in current validated revision")
        data = _asset(self.project, f"revisions/{revision}/{name}").read_bytes()
        if digest(data) != manifest["files"][name]:
            raise ProjectError("Stale mask hash")
        with Image.open(io.BytesIO(data)) as image:
            array = np.array(image)
        if label == "support":
            array = np.rint(array.astype(np.float64) / 257).astype(np.uint8)
        buffer = io.BytesIO()
        Image.fromarray(array).save(buffer, format="PNG")
        return buffer.getvalue()


class ReviewHandler(BaseHTTPRequestHandler):
    server: ReviewServer

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, format: str, *args: Any) -> None:
        # Never log capability headers or current photo paths.
        pass

    def reply(self, status: int, body: bytes, content_type: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'self' 'sha256-"
            + self.script_hash
            + "'; style-src 'unsafe-inline'; img-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
        )
        self.end_headers()
        self.wfile.write(body)

    @property
    def script_hash(self) -> str:
        page = files("blackmask").joinpath("ui/review.html").read_bytes()
        script = page.split(b"<script>", 1)[1].split(b"</script>", 1)[0]
        return base64.b64encode(hashlib.sha256(script).digest()).decode()

    def allowed(self, private: bool) -> bool:
        if self.headers.get_all("Host") != [self.server.host]:
            return False
        origin = self.headers.get_all("Origin")
        if origin is not None and origin != [self.server.origin]:
            return False
        if self.headers.get("Sec-Fetch-Site") in ("cross-site", "same-site"):
            return False
        return not (private and self.headers.get_all("X-Blackmask-Token") != [self.server.token])

    def error(self, status: int, message: str) -> None:
        self.reply(status, json.dumps({"error": message}, allow_nan=False).encode())

    def do_GET(self) -> None:
        if not self.allowed(self.path not in {"/", "/coordinates.js"}):
            self.error(403, "Forbidden host, origin or capability")
            return
        try:
            if self.path == "/":
                self.reply(
                    200,
                    files("blackmask").joinpath("ui/review.html").read_bytes(),
                    "text/html; charset=utf-8",
                )
            elif self.path == "/coordinates.js":
                self.reply(
                    200,
                    files("blackmask").joinpath("ui/coordinates.js").read_bytes(),
                    "text/javascript; charset=utf-8",
                )
            elif self.path == "/api/state":
                self.reply(200, json.dumps(self.server.snapshot(), allow_nan=False).encode())
            elif self.path.startswith("/image/"):
                self.reply(200, self.server.image(self.path), "image/png")
            elif self.path.startswith("/mask/"):
                self.reply(200, self.server.mask(self.path), "image/png")
            else:
                self.error(404, "Unknown route")
        except FileNotFoundError:
            self.error(404, "Unknown asset identity")
        except (OSError, ValueError, TypeError, KeyError) as error:
            self.error(409, str(error))

    def do_POST(self) -> None:
        if not self.allowed(True) or self.headers.get_all("Origin") != [self.server.origin]:
            self.error(403, "Forbidden host, origin or capability")
            return
        if self.path != "/api/action":
            self.error(404, "Unknown route")
            return
        if self.headers.get_all("Content-Type") != ["application/json"] or self.headers.get(
            "Transfer-Encoding"
        ):
            self.error(400, "Expected bounded application/json body")
            return
        try:
            lengths = self.headers.get_all("Content-Length")
            if not lengths or len(lengths) != 1 or not lengths[0].isdigit():
                raise ValueError("Missing/invalid body length")
            size = int(lengths[0])
            if not 0 < size <= 2_000_000:
                self.error(413, "Body too large or empty")
                return
            body = self.rfile.read(size)
            if len(body) != size:
                raise ValueError("Incomplete body")
            data = json.loads(
                body,
                parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite JSON")),
            )
            self.server.start_action(data)
            self.reply(202, b'{"started":true}')
        except (OSError, ValueError, TypeError) as error:
            self.error(409 if "busy" in str(error).lower() else 400, str(error))


def open_viewer(
    project: Path, model_cache: Path | None = None, sam_cache: Path | None = None
) -> None:
    with ReviewServer(project, model_cache, sam_cache) as server:
        url = server.origin + "/#" + server.token
        print("Local review window: " + url, flush=True)
        webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
