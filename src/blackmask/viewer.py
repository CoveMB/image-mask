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
from .export import export_project, render_background, render_black, saved_layers
from .framing import (
    FramingSaveUncertain,
    framing_preview,
    read_framing_preset,
    save_framing_preset,
    validate_margins,
)
from .guidance import coordinates
from .project import (
    ProjectError,
    _asset,
    _json_bytes,
    _root,
    _validate_assets,
    _validation_scope,
    accept_development,
    digest,
    read_project,
    read_revision,
)
from .review import review_panels
from .series_framing import (
    SeriesSaveUncertain,
    _unique_object,
    compute_series_layout,
    parse_series_preset,
    portable_series_preset,
    read_series_settings,
    render_series,
    save_series_settings,
    series_sampling_plan,
    validate_series_settings,
)


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
        self.framing_preview_lock = threading.Lock()
        self.action: dict[str, Any] = {"running": False, "error": None, "result": None}
        super().__init__(("127.0.0.1", 0), ReviewHandler)
        self.origin = f"http://127.0.0.1:{self.server_port}"
        self.host = f"127.0.0.1:{self.server_port}"

    @_validation_scope()
    def snapshot(self) -> dict[str, Any]:
        # Capture action first: completion must never be paired with pre-action state.
        action = dict(self.action)
        # State pointers may advance during an active writer. Keep the established
        # action-first polling contract; only bind immutable source/revision bytes.
        captured = {"source.json": _asset(self.project, "source.json").read_bytes()}
        state = operations.operation_status(self.project)
        master, _ = _validate_assets(self.project, state, validate_drafts=False)
        height, width = master.shape[:2]
        state.update(
            dimensions_wh=[width, height],
            source_url=f"/image/source/{state['master_id']}/0,0,{width},{height}",
        )
        state["action"] = action
        state.update(framing=None, framing_digest=None, framing_error=None)
        try:
            margins, preset_digest = read_framing_preset(
                self.project, state["master_id"], (width, height)
            )
            state.update(framing=margins.to_dict(), framing_digest=preset_digest)
        except (OSError, ValueError, TypeError) as error:
            state["framing_error"] = str(error)
        state.update(series_settings=None, series_digest=None, series_error=None)
        try:
            settings, preset_digest = read_series_settings(
                self.project, state["master_id"], (width, height)
            )
            state.update(series_settings=settings.to_dict(), series_digest=preset_digest)
        except (OSError, ValueError, TypeError) as error:
            state["series_error"] = str(error)
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
                manifest, raw = self._validated_revision(path.name, state["master_id"])
                captured[f"revisions/{path.name}/manifest.json"] = raw
                exposure_area = None
                if manifest.get("local_exposure", {}).get("area_sha256"):
                    exposure_area = json.loads(
                        _asset(
                            self.project, f"revisions/{path.name}/effects/exposure/area.json"
                        ).read_bytes()
                    )
                fade_area = None
                if manifest.get("shadow_fade", {}).get("area_sha256"):
                    fade_area = json.loads(
                        _asset(
                            self.project, f"revisions/{path.name}/effects/shadow-fade/area.json"
                        ).read_bytes()
                    )
                exposure = dict(manifest.get("local_exposure", {"enabled": False, "stale": False}))
                if "local_exposure" in manifest and manifest["final_acceptable"]:
                    saved_review = json.loads(
                        _asset(
                            self.project, f"revisions/{path.name}/review/manifest.json"
                        ).read_bytes()
                    )
                    exposure["clipping"] = saved_review["local_exposure_clipping"]
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
                        "revision_manifest_sha256": digest(raw),
                        "color_cleanup": manifest.get(
                            "color_cleanup", {"enabled": False, "stale": False}
                        ),
                        "shading": manifest.get("shading", {"enabled": False, "stale": False}),
                        "local_exposure": exposure,
                        "exposure_area": exposure_area,
                        "shadow_fade": manifest.get(
                            "shadow_fade", {"enabled": False, "stale": False}
                        ),
                        "shadow_fade_area": fade_area,
                        "background": manifest.get("background"),
                        "tile_summary": {
                            k: manifest.get("model", {}).get(k)
                            for k in ("inferred_tiles", "reused_tiles")
                        },
                    }
                )
        state["revisions"] = revisions
        if any(_asset(self.project, name).read_bytes() != raw for name, raw in captured.items()):
            raise ProjectError("Stale snapshot source or revision manifest; retry")
        return state

    def _validated_revision(self, revision: str, source_id: str) -> tuple[dict[str, Any], bytes]:
        if not isinstance(revision, str) or re.fullmatch(r"rev-[0-9]{3,}", revision) is None:
            raise ProjectError("Invalid saved revision identity")
        path = _asset(self.project, f"revisions/{revision}/manifest.json")
        raw = path.read_bytes()
        manifest = read_revision(self.project, revision, source_id)
        if _json_bytes(json.loads(raw)) != _json_bytes(manifest) or path.read_bytes() != raw:
            raise ProjectError("Stale revision manifest; reload current project")
        return manifest, raw

    @_validation_scope()
    def preview_framing(self, data: Any, *, series_mode: bool = False) -> dict[str, Any]:
        """Read-only final-result preview; never author or publish native assets."""
        if (
            not isinstance(data, dict)
            or set(data)
            != {
                "master_id",
                "revision",
                "revision_manifest_sha256",
                "settings" if series_mode else "margins",
            }
            or not isinstance(data["revision_manifest_sha256"], str)
            or re.fullmatch("[a-f0-9]{64}", data["revision_manifest_sha256"]) is None
        ):
            raise ValueError("Invalid framing preview structured fields")
        if not self.framing_preview_lock.acquire(blocking=False):
            raise ProjectError("Framing preview busy; retry after the current preview")
        try:
            captured = {
                name: _asset(self.project, name).read_bytes()
                for name in ("state.json", "source.json")
            }
            state = read_project(self.project, validate_drafts=False)
            if state["master_id"] != data["master_id"]:
                raise ProjectError("Stale framing preview source")
            manifest, raw = self._validated_revision(data["revision"], state["master_id"])
            if digest(raw) != data["revision_manifest_sha256"]:
                raise ProjectError("Stale framing preview revision manifest")
            captured[f"revisions/{data['revision']}/manifest.json"] = raw
            from .background import read_background
            from .effects import effects_stale, saved_shading

            if effects_stale(manifest):
                raise ProjectError("Stale enabled appearance; rebuild or disable before preview")
            source, _ = _validate_assets(self.project, state, validate_drafts=False)
            settings_record: dict[str, object] = {}
            if series_mode:
                series_settings = validate_series_settings(data["settings"])
                settings_record.update(series_settings.to_dict())
            else:
                margins = validate_margins(data["margins"], (source.shape[1], source.shape[0]))
                settings_record.update(margins.to_dict())
            del source
            foreground, alpha, loaded_manifest = saved_layers(
                self.project, data["revision"], state["master_id"]
            )
            if _json_bytes(loaded_manifest) != _json_bytes(manifest):
                raise ProjectError("Stale framing preview saved layers")
            weight, opacity = saved_shading(self.project, data["revision"], alpha, loaded_manifest)
            background = read_background(
                _asset(self.project, f"revisions/{data['revision']}"), loaded_manifest
            )
            geometry: dict[str, object]
            if series_mode:
                layout = compute_series_layout(alpha, series_settings)
                width, height = layout.output_dimensions_wh
                longest = max(width, height)
                display = (
                    max(1, int(width * min(1600, longest) / longest)),
                    max(1, int(height * min(1600, longest) / longest)),
                )
                sampling = series_sampling_plan(layout, display_dimensions_wh=display)
                del background
                rgb16 = render_series(
                    foreground,
                    alpha,
                    sampling,
                    weight16=weight,
                    opacity=opacity,
                    background_settings=loaded_manifest.get("background", {}).get("settings"),
                )
                pixels = np.empty((*rgb16.shape[:2], 3), np.uint8)
                for start in range(0, pixels.shape[0], 64):
                    pixels[start : start + 64] = np.rint(
                        rgb16[start : start + 64].astype(np.float64) / 257
                    ).astype(np.uint8)
                del rgb16
                geometry = {
                    "layout": layout.to_dict(),
                    "output_dimensions_wh": [width, height],
                    "display_dimensions_wh": list(display),
                    "source_dimensions_wh": [foreground.shape[1], foreground.shape[0]],
                }
            else:
                native = (
                    render_black(foreground, alpha, weight, opacity)
                    if background is None
                    else render_background(foreground, alpha, background, weight, opacity)
                )
                pixels, geometry = framing_preview(native, background, margins)
            with io.BytesIO() as buffer:
                image = Image.fromarray(pixels)
                try:
                    image.save(buffer, format="PNG")
                finally:
                    image.close()
                png_base64 = base64.b64encode(buffer.getvalue()).decode("ascii")
            self._validated_revision(data["revision"], state["master_id"])
            if any(
                _asset(self.project, name).read_bytes() != value for name, value in captured.items()
            ):
                raise ProjectError("Stale framing preview inputs changed while rendering")
            return {
                "master_id": state["master_id"],
                "revision": data["revision"],
                "revision_manifest_sha256": digest(raw),
                "settings" if series_mode else "margins": settings_record,
                **geometry,
                "algorithm": "series-lanczos-premultiplied-v1"
                if series_mode
                else "saved-backdrop-edge-padding-v1",
                "label": "RGB8 approximate resized series preview; reduced detail, inspect exported TIFF"
                if series_mode
                else "RGB8 sampled layout preview; reduced detail, not a native editing view",
                "png_base64": png_base64,
            }
        finally:
            self.framing_preview_lock.release()

    def validate_series_preset(self, data: Any) -> dict[str, Any]:
        if (
            not isinstance(data, dict)
            or set(data) != {"preset_json"}
            or not isinstance(data["preset_json"], str)
        ):
            raise ValueError("Portable series validation requires only preset_json text")
        settings = parse_series_preset(data["preset_json"].encode("utf-8"))
        return {
            "settings": settings.to_dict(),
            "preset_json": portable_series_preset(settings).decode("utf-8"),
        }

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
            "effects": {"scope_xyxy", "candidate_comparison"},
            "repair": {"context_xyxy", "scope_xyxy", "reason", "merge_policy"},
            "restore": {"revision", "replace_drafts"},
            "resume": {"operation_id"},
            "export": {"revision", "draft"},
            "framing-save": {"margins", "expected_digest"},
            "series-save": {"settings", "expected_digest"},
            "series-export": {
                "revision",
                "draft",
                "revision_manifest_sha256",
                "settings",
                "transparent",
            },
        }
        if action == "export":
            fields["export"] |= set(data) & {"framing", "framed_transparent"}
        if action == "effects":
            optional = {
                "support_file",
                "color_cleanup",
                "shading",
                "shading_protection_file",
                "opacity_only",
                "local_exposure",
                "exposure_area",
                "exposure_protection_file",
                "exposure_amount_only",
                "shadow_fade",
                "shadow_fade_area",
                "shadow_fade_protection_file",
                "shadow_fade_amount_only",
                "background",
            }
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
            except Exception as error:  # noqa: BLE001 - report all ordinary failures to the page.
                self.action["error"] = str(error).strip() or type(error).__name__
                if isinstance(error, (FramingSaveUncertain, SeriesSaveUncertain)):
                    self.action["result"] = error.visible
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
            return export_project(
                self.project,
                revision=data["revision"],
                draft=data["draft"],
                framing=data.get("framing"),
                framed_transparent=data.get("framed_transparent", False),
            )
        if action == "framing-save":
            return save_framing_preset(
                self.project,
                data["margins"],
                expected_digest=data["expected_digest"],
                expected_source_id=data["master_id"],
            )
        if action == "series-save":
            return save_series_settings(
                self.project,
                data["settings"],
                expected_digest=data["expected_digest"],
                expected_source_id=data["master_id"],
            )
        if action == "series-export":
            if (
                not isinstance(data["revision"], str)
                or not data["revision"]
                or type(data["draft"]) is not bool
                or type(data["transparent"]) is not bool
            ):
                raise ProjectError(
                    "Series export requires an explicit selected revision and boolean variant/draft flags"
                )
            return export_project(
                self.project,
                revision=data["revision"],
                draft=data["draft"],
                series=data["settings"],
                framed_transparent=data["transparent"],
                expected_master_id=data["master_id"],
                expected_revision_manifest_sha256=data["revision_manifest_sha256"],
            )
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
                        "local_exposure",
                        "exposure_area",
                        "exposure_protection_file",
                        "exposure_amount_only",
                        "shadow_fade",
                        "shadow_fade_area",
                        "shadow_fade_protection_file",
                        "shadow_fade_amount_only",
                        "background",
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
            r"/image/(source|result|black|gray|white|alpha)/([a-f0-9]{64}|rev-[0-9]{3,})/([0-9]+,[0-9]+,[0-9]+,[0-9]+)(/base|/exposure-off|/shadow-fade-off|/p(?:0|0.12|0.24))?",
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
                exposure_off=base == "/exposure-off",
                shadow_fade_off=base == "/shadow-fade-off",
            )
            weight, opacity = saved_shading(
                self.project, identity, alpha, manifest, effects_off=bool(base == "/base" or stale)
            )
            if base and base.startswith("/p") and weight is not None:
                opacity = float(base[2:])
            from .background import read_background

            background = (
                read_background(_asset(self.project, f"revisions/{identity}"), manifest)
                if panel == "result" and not (base == "/base" or stale or effects_stale(manifest))
                else None
            )
            pixels = review_panels(
                source[y0:y1, x0:x1],
                foreground[y0:y1, x0:x1],
                alpha[y0:y1, x0:x1],
                None if weight is None else weight[y0:y1, x0:x1],
                opacity,
                background16=None if background is None else background[y0:y1, x0:x1],
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
        if self.path not in {
            "/api/action",
            "/api/framing-preview",
            "/api/series-preview",
            "/api/series-preset-validate",
        }:
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
                object_pairs_hook=_unique_object if self.path.startswith("/api/series-") else None,
                parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite JSON")),
            )
            if self.path == "/api/framing-preview":
                result = self.server.preview_framing(data)
                self.reply(200, json.dumps(result, allow_nan=False).encode())
            elif self.path == "/api/series-preview":
                result = self.server.preview_framing(data, series_mode=True)
                self.reply(200, json.dumps(result, allow_nan=False).encode())
            elif self.path == "/api/series-preset-validate":
                self.reply(
                    200,
                    json.dumps(self.server.validate_series_preset(data), allow_nan=False).encode(),
                )
            else:
                if isinstance(data, dict) and data.get("action") in {
                    "series-save",
                    "series-export",
                }:
                    data = json.loads(
                        body,
                        object_pairs_hook=_unique_object,
                        parse_constant=lambda value: (_ for _ in ()).throw(
                            ValueError("Nonfinite JSON")
                        ),
                    )
                self.server.start_action(data)
                self.reply(202, b'{"started":true}')
        except (OSError, ValueError, TypeError) as error:
            conflict = "busy" in str(error).lower() or (
                self.path in {"/api/framing-preview", "/api/series-preview"}
                and isinstance(error, ProjectError)
            )
            self.error(409 if conflict else 400, str(error))


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
