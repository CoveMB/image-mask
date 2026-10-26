"""Requested delivery contracts, preserving native data and exact saved rendering."""

import importlib
import json
from pathlib import Path

import numpy as np
import pytest
import tifffile
from PIL import Image
from test_effects import fixture_project
from test_framing import hashes, margins, protected_project, scalar_composite

from blackmask.export import export_project, saved_layers
from blackmask.ingest import srgb_profile
from blackmask.project import ProjectError, read_project

DEFAULT_MEMBERS = {
    "result_rgb16.tif",
    "result_RGB8_VIEW.png",
    "recipe.toml",
    "manifest.json",
    "README.txt",
}


def mode_arguments(mode):
    if mode == "add-margins":
        return {"framing": margins(1, 2, 2, 1)}
    if mode == "match-series":
        return {
            "series": {
                "name": "Small",
                "output_width_px": 40,
                "output_height_px": 50,
                "side_margin_tenths_percent": 150,
                "minimum_vertical_margin_tenths_percent": 50,
            }
        }
    return {}


@pytest.mark.parametrize("mode", ["native", "add-margins", "match-series"])
def test_default_result_delivery_is_compact_and_profiled(tmp_path, mode):
    project, _, _ = protected_project(tmp_path)
    preserved = hashes(project)
    output = export_project(project, **mode_arguments(mode))
    directory = Path(output["directory"])
    assert {p.name for p in directory.iterdir()} == DEFAULT_MEMBERS
    with tifffile.TiffFile(directory / "result_rgb16.tif") as image:
        page = image.pages[0]
        assert page.dtype == np.dtype("uint16") and page.compression == 1
        assert page.tags[34675].value == srgb_profile()
        pixels = page.asarray()
    if mode == "native":
        assert pixels.shape == (4, 6, 3), "Native delivery must retain full source pixel dimensions"
    with Image.open(directory / "result_RGB8_VIEW.png") as image:
        assert image.mode == "RGB" and image.info["icc_profile"] == srgb_profile()
        np.testing.assert_array_equal(np.array(image), np.rint(pixels / 257).astype(np.uint8))
    assert all(hashes(project)[name] == value for name, value in preserved.items())


@pytest.mark.parametrize("mode", ["native", "add-margins", "match-series"])
def test_intact_delivery_reuses_before_render_or_stage(tmp_path, monkeypatch, mode):
    project, _, _ = protected_project(tmp_path)
    arguments = mode_arguments(mode)
    first = export_project(project, **arguments)
    preserved = hashes(project)

    def forbidden(*args, **kwargs):
        raise AssertionError("Intact export must not compute or stage output")

    export = importlib.import_module("blackmask.export")
    for module, names in (
        (export, ["render_black", "render_background", "view_rgba", "check_space"]),
        (importlib.import_module("blackmask.framing"), ["frame_result", "frame_transparent"]),
        (importlib.import_module("blackmask.series_framing"), ["render_series"]),
        (importlib.import_module("blackmask.exposure"), ["apply_exposure"]),
        (importlib.import_module("blackmask.shadow_fade"), ["apply_shadow_fade"]),
        (importlib.import_module("tempfile"), ["mkdtemp"]),
    ):
        for name in names:
            monkeypatch.setattr(module, name, forbidden)
    repeated = export_project(project, **arguments)
    assert repeated["reused"] is True and first["reused"] is False
    assert {k: v for k, v in repeated.items() if k != "reused"} == {
        k: v for k, v in first.items() if k != "reused"
    }
    assert hashes(project) == preserved


@pytest.mark.parametrize(
    "arguments",
    [
        {"framing": margins(0, 0, 0, 0)},
        mode_arguments("add-margins"),
        mode_arguments("match-series"),
    ],
)
def test_editable_presentation_request_delivers_explicit_native_pair(tmp_path, arguments):
    project, _, _ = fixture_project(tmp_path)
    response = export_project(project, variants=("editable",), **arguments)
    primary = Path(response["directory"])
    native = Path(response["editable_companion"]["directory"])
    assert {p.name for p in primary.iterdir()} == DEFAULT_MEMBERS
    record = json.loads((primary / "manifest.json").read_bytes())
    child = json.loads((native / "manifest.json").read_bytes())
    assert child["mode"] == "native" and child["requested_variants"] == ["editable"]
    assert record["editable_companion_request"] == {
        "identity_sha256": child["identity_sha256"],
        "directory_name": native.name,
    }
    assert {"foreground_rgb16.tif", "source_rgb16.tif", "alpha16.png"} <= {
        p.name for p in native.iterdir()
    }


@pytest.mark.parametrize("damage", ["absent", "corrupt", "rehashed", "symlink", "intact"])
@pytest.mark.parametrize("mode", ["add-margins", "match-series"])
def test_pair_lookup_precedes_producers_and_requires_exact_child(
    tmp_path, monkeypatch, damage, mode
):
    project, _, _ = fixture_project(tmp_path)
    arguments = {**mode_arguments(mode), "variants": ("editable",)}
    first = export_project(project, **arguments)
    native = Path(first["editable_companion"]["directory"])
    if damage == "absent":
        native.rename(tmp_path / "preserved-native")
    elif damage == "corrupt":
        (native / "foreground_rgb16.tif").write_bytes(b"corrupt synthetic child")
    elif damage == "rehashed":
        from blackmask.ingest import write_developed
        from blackmask.project import _json_bytes, digest

        member = native / "foreground_rgb16.tif"
        pixels = tifffile.imread(member)
        pixels[0, 0, 0] ^= 1
        write_developed(member, pixels)
        manifest = json.loads((native / "manifest.json").read_bytes())
        manifest["files"][member.name].update(
            sha256=digest(member.read_bytes()), bytes=member.stat().st_size
        )
        (native / "manifest.json").write_bytes(_json_bytes(manifest))
    elif damage == "symlink":
        preserved_native = tmp_path / "preserved-native"
        native.rename(preserved_native)
        native.symlink_to(preserved_native, target_is_directory=True)
    preserved = hashes(project)

    def forbidden(*args, **kwargs):
        raise AssertionError("Pair lookup must precede selection/render/stage/publication")

    export = importlib.import_module("blackmask.export")
    for module, names in (
        (
            export,
            [
                "_export_native_locked",
                "render_black",
                "render_background",
                "view_rgba",
                "_publish_new_directory",
                "check_space",
            ],
        ),
        (importlib.import_module("blackmask.effects"), ["selected_foreground"]),
        (importlib.import_module("blackmask.series_framing"), ["render_series"]),
        (importlib.import_module("tempfile"), ["mkdtemp"]),
    ):
        for name in names:
            monkeypatch.setattr(module, name, forbidden)
    if damage == "intact":
        repeated = export_project(project, **arguments)
        assert repeated["reused"] and repeated["directory"] == first["directory"]
        assert repeated["editable_companion"] == first["editable_companion"]
    else:
        with pytest.raises(ProjectError, match="Incomplete|collision|companion|symlink") as error:
            export_project(project, **arguments)
        if damage == "absent":
            assert str(native) in str(error.value)
            assert first["directory"] in str(error.value)
    assert hashes(project) == preserved
    assert native.exists() == (damage != "absent")
    assert native.is_symlink() == (damage == "symlink")


@pytest.mark.parametrize("mode", ["add-margins", "match-series"])
def test_native_only_partial_reuses_child_without_native_producer(tmp_path, monkeypatch, mode):
    project, _, _ = fixture_project(tmp_path)
    arguments = {**mode_arguments(mode), "variants": ("editable",)}
    first = export_project(project, **arguments)
    primary = Path(first["directory"])
    native = Path(first["editable_companion"]["directory"])
    preserved = hashes(native)
    primary.rename(tmp_path / "preserved-primary")

    def forbidden(*args, **kwargs):
        raise AssertionError("Valid native-only partial must reuse its exact native child")

    monkeypatch.setattr(
        importlib.import_module("blackmask.export"), "_export_native_locked", forbidden
    )
    repeated = export_project(project, **arguments)
    assert repeated["directory"] == first["directory"] and not repeated["reused"]
    assert repeated["editable_companion"] == first["editable_companion"]
    assert hashes(native) == preserved


@pytest.mark.parametrize("mode", ["native", "add-margins", "match-series"])
@pytest.mark.parametrize("enabled", [False, True])
def test_saved_spatial_record_does_not_opt_into_editable_delivery(tmp_path, mode, enabled):
    from test_spatial_fade import spatial_request, spatial_settings

    from blackmask.operations import apply_operation

    project, _, _ = fixture_project(tmp_path)
    settings = spatial_settings(6, 4)
    settings["enabled"] = enabled
    result = apply_operation(project, spatial_request(project, settings))
    output = export_project(
        project, revision=result["revision"], draft=True, **mode_arguments(mode)
    )
    assert "editable_companion" not in output
    assert {p.name for p in Path(output["directory"]).iterdir()} == DEFAULT_MEMBERS


@pytest.mark.parametrize("mode", ["native", "add-margins", "match-series"])
@pytest.mark.parametrize("variants", [("black",), ("transparent",), ("transparent", "black")])
def test_requested_variants_do_not_generate_unselected_outputs(tmp_path, mode, variants):
    project, _, _ = protected_project(tmp_path)
    first = export_project(project, variants=variants, **mode_arguments(mode))
    directory = Path(first["directory"])
    expected = (
        DEFAULT_MEMBERS
        | ({"black_rgb16.tif", "black_RGB8_VIEW.png"} if "black" in variants else set())
        | ({"transparent_RGBA8_VIEW.png"} if "transparent" in variants else set())
    )
    assert {p.name for p in directory.iterdir()} == expected
    record = json.loads((directory / "manifest.json").read_bytes())
    for name in expected - {"manifest.json", "recipe.toml", "README.txt"}:
        assert record["files"][name]["dimensions_wh"] == record["output_dimensions_wh"]
    repeated = export_project(project, variants=tuple(reversed(variants)), **mode_arguments(mode))
    assert repeated["directory"] == first["directory"] and repeated["reused"]


@pytest.mark.parametrize("shading_state", ["enabled", "disabled", "absent"])
def test_native_editable_delivery_reconstructs_from_independent_layers(tmp_path, shading_state):
    import shutil
    import subprocess
    import sys

    from test_effects import shading_request
    from test_ingest import saved_raster

    from blackmask import operations
    from blackmask.background import read_background
    from blackmask.effects import saved_shading

    project, _, selected = (
        fixture_project(tmp_path) if shading_state == "absent" else protected_project(tmp_path)
    )
    if shading_state == "disabled":
        selected = operations.apply_operation(
            project, shading_request(project, enabled=False, opacity=0.37, opacity_only=True)
        )
        operations.accept_revision(project, selected["revision"])
    state = read_project(project)
    foreground, alpha, manifest = saved_layers(project, selected["revision"], state["developed_id"])
    weight, opacity = saved_shading(project, selected["revision"], alpha, manifest)
    background = read_background(project, project / "revisions" / selected["revision"], manifest)
    expected = scalar_composite(foreground, alpha, background, weight, opacity)
    result = export_project(project, variants=("editable",))
    directory = Path(result["directory"])
    assert not (directory / "black_rgb16.tif").exists()
    assert not (directory / "transparent_RGBA8_VIEW.png").exists()
    delivered_f = tifffile.imread(directory / "foreground_rgb16.tif")
    with Image.open(directory / "alpha16.png") as image:
        delivered_a = np.array(image)
        assert "icc_profile" not in image.info and "gamma" not in image.info
    if shading_state == "absent":
        assert not (directory / "shadow_weight16.png").exists()
        delivered_w = np.zeros_like(delivered_a)
    else:
        with Image.open(directory / "shadow_weight16.png") as image:
            delivered_w = np.array(image)
    delivered_b = tifffile.imread(directory / "background_rgb16.tif")
    record = json.loads((directory / "manifest.json").read_bytes())
    shading = record.get("shading", {})
    effective_opacity = shading["opacity"] if shading.get("enabled", False) else 0.0
    actual = scalar_composite(delivered_f, delivered_a, delivered_b, delivered_w, effective_opacity)
    np.testing.assert_array_equal(actual, expected)
    np.testing.assert_array_equal(tifffile.imread(directory / "result_rgb16.tif"), expected)
    partial_alpha = 16384 if shading_state == "absent" else 32768
    assert np.any(delivered_a == partial_alpha) and np.any(delivered_f % 257)
    if shading_state != "absent":
        assert np.any(delivered_w) and shading["opacity"] == 0.37
        settings = json.loads((directory / "shading_settings.json").read_bytes())
        assert settings["enabled"] is (shading_state == "enabled")
        assert settings["opacity"] == shading["opacity"]
        with Image.open(
            saved_raster(project / "revisions" / selected["revision"] / "supports/protection.png")
        ) as image:
            protected = np.array(image) != 0
        assert np.any(protected & (delivered_a > 0) & (delivered_a < 65535))
    if shading_state == "disabled":
        wrong_saved_opacity = scalar_composite(
            delivered_f, delivered_a, delivered_b, delivered_w, shading["opacity"]
        )
        assert np.any(wrong_saved_opacity != expected), "OFF must ignore retained nonzero W/p"
    assert (
        "use opacity 0 when shading is disabled or absent" in (directory / "README.txt").read_text()
    )
    standalone = tmp_path / "standalone-editable"
    shutil.copytree(directory, standalone)
    program = """import json,sys
from pathlib import Path
import numpy as np,tifffile
from PIL import Image
p=Path(sys.argv[1]); record=json.loads((p/'manifest.json').read_bytes())
f=tifffile.imread(p/'foreground_rgb16.tif').astype(np.float64)
with Image.open(p/'alpha16.png') as image: a=np.array(image).astype(np.float64)/65535
w=np.zeros(a.shape,dtype=np.float64)
if (p/'shadow_weight16.png').exists():
 with Image.open(p/'shadow_weight16.png') as image: w=np.array(image).astype(np.float64)/65535
b=tifffile.imread(p/'background_rgb16.tif').astype(np.float64)
shading=record.get('shading',{})
effective_opacity=shading['opacity'] if shading.get('enabled',False) else 0.0
assert 'use opacity 0 when shading is disabled or absent' in (p/'README.txt').read_text()
recovered=np.rint(f*a[...,None]*(1-effective_opacity*w[...,None])+b*(1-a[...,None])).astype(np.uint16)
np.testing.assert_array_equal(recovered,tifffile.imread(p/'result_rgb16.tif'))
assert np.any((a>0)&(a<1))
print('standalone saved native operands reconstructed without application/project/model/cache')
"""
    completed = subprocess.run(
        [sys.executable, "-B", "-c", program, str(standalone)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "standalone saved native operands reconstructed" in completed.stdout


@pytest.mark.parametrize("mode", ["native", "add-margins", "match-series"])
@pytest.mark.parametrize(
    "prior_version", ["requested-result-v1", "requested-result-v2", "requested-result-v3"]
)
def test_corrected_notes_use_new_identity_preserving_prior_version(
    tmp_path, monkeypatch, mode, prior_version
):
    project, _, _ = protected_project(tmp_path)
    export = importlib.import_module("blackmask.export")
    arguments = mode_arguments(mode)
    with monkeypatch.context() as previous:
        previous.setattr(export, "EXPORT_VERSION", prior_version)
        prior = export_project(project, variants=("transparent",), **arguments)
    preserved = hashes(Path(prior["directory"]))
    output = export_project(project, variants=("transparent",), **arguments)
    record = json.loads(Path(output["manifest_file"]).read_bytes())
    assert record["export_version"] == "requested-result-v4"
    assert record["encoding"]["version"] == "requested-result-v4"
    assert output["directory"] != prior["directory"] and not output["reused"]
    assert hashes(Path(prior["directory"])) == preserved
    with tifffile.TiffFile(Path(prior["directory"]) / "result_rgb16.tif") as old_image:
        np.testing.assert_array_equal(
            old_image.asarray(), tifffile.imread(Path(output["directory"]) / "result_rgb16.tif")
        )
    notes = (Path(output["directory"]) / "README.txt").read_text()
    assert "use opacity 0 when shading is disabled or absent" in notes
    assert "effective p" in record["views"]
    assert export_project(project, variants=("transparent",), **arguments)["reused"]


@pytest.mark.parametrize("mode", ["native", "add-margins", "match-series"])
@pytest.mark.parametrize("editable", [False, True])
@pytest.mark.parametrize("appearance", ["legacy", "sharpening", "spatial"])
def test_sharpening_notes_change_identity_without_rewriting_prior_v4(
    tmp_path, monkeypatch, mode, editable, appearance
):
    from test_sharpening import sharpening_project, sharpening_request
    from test_spatial_fade import spatial_request

    from blackmask import operations
    from blackmask.project import _json_bytes, digest

    project, _, _ = sharpening_project(tmp_path)
    if appearance != "legacy":
        operations.apply_operation(project, sharpening_request(project))
    if appearance == "spatial":
        operations.apply_operation(project, spatial_request(project, candidate=True))
    export = importlib.import_module("blackmask.export")
    current_request = export._delivery_request_record
    current_notes = export._delivery_notes
    old_warning = (
        "Selected foreground already includes local exposure and Shadow fade; apply neither again. "
    )
    new_warning = "Selected foreground already includes Local sharpening, local exposure and Shadow fade; apply none again. "

    def previous_request(*args, **kwargs):
        record = current_request(*args, **kwargs)
        # Freeze the published v4 descriptions, including its spatial branch.
        record["views"] = (
            "RGB8/RGBA8 reduced color/alpha precision; straight RGB is not alpha-multiplied; selected saved foreground; baked shading at effective p (saved p when enabled, 0 when disabled or absent); editable W16 plus p retained separately only when requested"
        )
        if record["mode"] == "native":
            record["result_compositing"] = (
                "round(blend_linear_srgb(F,B,q)*A+B*(1-A)); q from delivered combined W16, explicit protection and independent highlight preservation; exact q=0/q=1 endpoints"
                if appearance == "spatial"
                else "encoded-sRGB float64 round ties-to-even(F*A*H+B*(1-A)); H=1-p*W16/65535, A=alpha16/65535; p is saved opacity only when shading is enabled, otherwise zero; B is saved background RGB16 or zero; F already includes local exposure and Shadow fade"
            )
        record.pop("identity_sha256")
        record["identity_sha256"] = digest(_json_bytes(record))
        return record

    def previous_notes(record):
        return current_notes(record).replace(new_warning.encode(), old_warning.encode())

    arguments = dict(
        revision=read_project(project)["working_revision"],
        draft=True,
        variants=("editable",) if editable else (),
        **mode_arguments(mode),
    )
    with monkeypatch.context() as previous:
        previous.setattr(export, "_delivery_request_record", previous_request)
        previous.setattr(export, "_delivery_notes", previous_notes)
        prior = export_project(project, **arguments)
    preserved = hashes(project)
    output = export_project(project, **arguments)
    assert output["directory"] != prior["directory"] and not output["reused"]
    current_hashes = hashes(project)
    assert all(current_hashes[name] == value for name, value in preserved.items())
    record = json.loads(Path(output["manifest_file"]).read_bytes())
    old_record = json.loads(Path(prior["manifest_file"]).read_bytes())
    assert record["export_version"] == old_record["export_version"] == "requested-result-v4"
    notes = (Path(output["directory"]) / "README.txt").read_text()
    assert new_warning in notes
    if mode == "native":
        assert (
            "F already includes Local sharpening, local exposure and Shadow fade"
            in record["result_compositing"]
        )
    np.testing.assert_array_equal(
        tifffile.imread(Path(output["directory"]) / "result_rgb16.tif"),
        tifffile.imread(Path(prior["directory"]) / "result_rgb16.tif"),
    )
    if editable and mode != "native":
        assert output["editable_companion"]["directory"] != prior["editable_companion"]["directory"]

    def forbidden(*args, **kwargs):
        raise AssertionError("A current intact delivery must reuse without staging/rendering")

    monkeypatch.setattr(export, "check_space", forbidden)
    monkeypatch.setattr(export.tempfile, "mkdtemp", forbidden)
    repeated = export_project(project, **arguments)
    assert repeated["reused"] and repeated["directory"] == output["directory"]


@pytest.mark.parametrize("variants", ["black", ("black", "black"), ("unknown",), (True,), None])
def test_invalid_variants_preserve_project(tmp_path, variants):
    project, _, _ = fixture_project(tmp_path)
    before = hashes(project)
    with pytest.raises(ValueError, match="variants"):
        export_project(project, variants=variants)
    assert hashes(project) == before


def test_png16_member_cannot_masquerade_as_png8(tmp_path):
    import hashlib
    import struct
    import zlib

    from blackmask.project import _json_bytes

    project, _, _ = protected_project(tmp_path)
    result = export_project(project)
    directory = Path(result["directory"])
    pixels = tifffile.imread(directory / "result_rgb16.tif")
    height, width = pixels.shape[:2]

    def chunk(kind, value):
        return (
            struct.pack(">I", len(value))
            + kind
            + value
            + struct.pack(">I", zlib.crc32(kind + value))
        )

    raw = b"\x89PNG\r\n\x1a\n"
    raw += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 16, 2, 0, 0, 0))
    raw += chunk(b"iCCP", b"sRGB\0\0" + zlib.compress(srgb_profile()))
    raw += chunk(
        b"IDAT", zlib.compress(b"".join(b"\0" + row.astype(">u2").tobytes() for row in pixels))
    )
    raw += chunk(b"IEND", b"")
    (directory / "result_RGB8_VIEW.png").write_bytes(raw)
    with Image.open(directory / "result_RGB8_VIEW.png") as image:
        assert image.mode == "RGB", "Pillow mode alone cannot establish the file bit depth"
    manifest_path = directory / "manifest.json"
    record = json.loads(manifest_path.read_bytes())
    record["files"]["result_RGB8_VIEW.png"].update(
        sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw)
    )
    manifest_path.write_bytes(_json_bytes(record))
    with pytest.raises(ProjectError, match="collision"):
        export_project(project)


@pytest.mark.parametrize("damage", ["numeric-draft", "non-rgb-tiff"])
def test_self_consistent_delivery_still_requires_exact_metadata_and_rgb_header(tmp_path, damage):
    import hashlib

    from blackmask.project import _json_bytes

    project, _, _ = fixture_project(tmp_path)
    result = export_project(project)
    directory = Path(result["directory"])
    manifest_path = directory / "manifest.json"
    record = json.loads(manifest_path.read_bytes())
    if damage == "numeric-draft":
        record["draft"] = 0  # Python equality alone equates this with False.
    else:
        path = directory / "result_rgb16.tif"
        pixels = tifffile.imread(path)
        tifffile.imwrite(
            path,
            pixels,
            photometric="minisblack",
            planarconfig="contig",
            extrasamples=[0, 0],
            metadata=None,
            extratags=[(34675, "B", len(srgb_profile()), srgb_profile(), False)],
        )
        with tifffile.TiffFile(path) as image:
            assert image.pages[0].shape == pixels.shape and image.pages[0].photometric != 2
        record["files"][path.name].update(
            bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest()
        )
    manifest_path.write_bytes(_json_bytes(record))
    before = hashes(directory)
    with pytest.raises(ProjectError, match="collision"):
        export_project(project)
    assert hashes(directory) == before


def test_late_reuse_rechecks_inputs_after_parent_sync_and_keeps_stage(tmp_path, monkeypatch):
    from test_framing import restore_delivery_after_staging

    project, _, _ = fixture_project(tmp_path)
    output = export_project(project)
    directory = Path(output["directory"])
    before = hashes(directory)
    restore_delivery_after_staging(monkeypatch, directory, tmp_path / "retained-delivery")
    export = importlib.import_module("blackmask.export")
    original = export._sync_directory

    def change_during_parent_sync(path):
        original(path)
        if path == project / "exports":
            source = project / "source.json"
            source.write_bytes(source.read_bytes() + b" ")

    monkeypatch.setattr(export, "_sync_directory", change_during_parent_sync)
    with pytest.raises(ProjectError, match="Stale"):
        export_project(project)
    assert hashes(directory) == before
    assert list((project / "exports").glob(".export-*"))


def test_default_native_export_uses_accepted_full_resolution_with_newer_draft(tmp_path):
    from test_effects import shading_request

    from blackmask import operations
    from blackmask.background import read_background
    from blackmask.effects import saved_shading

    project, _, accepted = protected_project(tmp_path)
    state = read_project(project)
    foreground, alpha, manifest = saved_layers(project, accepted["revision"], state["developed_id"])
    weight, opacity = saved_shading(project, accepted["revision"], alpha, manifest)
    backdrop = read_background(project, project / "revisions" / accepted["revision"], manifest)
    expected = scalar_composite(foreground, alpha, backdrop, weight, opacity)
    newer = operations.apply_operation(project, shading_request(project, opacity=0.12))
    assert newer["revision"] != accepted["revision"]
    before = (project / "state.json").read_bytes()
    result = export_project(project)
    assert result["revision"] == accepted["revision"] and result["draft"] is False
    directory = Path(result["directory"])
    actual = tifffile.imread(directory / "result_rgb16.tif")
    assert actual.dtype == np.uint16 and actual.shape == expected.shape == (4, 6, 3)
    np.testing.assert_array_equal(actual, expected)
    with Image.open(directory / "result_RGB8_VIEW.png") as image:
        assert image.size == (6, 4)
        np.testing.assert_array_equal(np.array(image), np.rint(expected / 257).astype(np.uint8))
    assert (project / "state.json").read_bytes() == before


@pytest.mark.parametrize("mode", ["native", "add-margins", "match-series"])
def test_prior_format_deliveries_are_preserved_without_legacy_lookup(tmp_path, mode):
    project, _, selected = fixture_project(tmp_path)
    exports = project / "exports"
    exports.mkdir()
    for name in (
        selected["revision"],
        selected["revision"] + "-framed-old",
        selected["revision"] + "-series-framed-old",
    ):
        old = exports / name
        old.mkdir()
        (old / "manifest.json").write_bytes(b"Incomplete prior format retained exactly")
    before = hashes(exports)
    output = export_project(project, **mode_arguments(mode))
    record = json.loads(Path(output["manifest_file"]).read_bytes())
    assert record["export_version"] == "requested-result-v4" and not output["reused"]
    assert all(hashes(exports)[name] == value for name, value in before.items())
    assert export_project(project, **mode_arguments(mode))["reused"]


@pytest.mark.parametrize("identity", ["encoding", "profile", "raw-manifest", "source-record"])
def test_execution_and_raw_input_identity_never_reuse_old_delivery(tmp_path, monkeypatch, identity):
    project, _, selected = fixture_project(tmp_path)
    first = export_project(project)
    before = hashes(Path(first["directory"]))
    export = importlib.import_module("blackmask.export")
    if identity in {"encoding", "profile"}:
        original = export._export_execution_identity

        def changed():
            value = original()
            value["png" if identity == "encoding" else "icc_profile_sha256"] = "different-runtime"
            return value

        monkeypatch.setattr(export, "_export_execution_identity", changed)
    else:
        path = (
            project / "source.json"
            if identity == "source-record"
            else project / "revisions" / selected["revision"] / "manifest.json"
        )
        path.write_bytes(path.read_bytes() + b" ")
    changed = export_project(project)
    assert changed["directory"] != first["directory"] and not changed["reused"]
    assert hashes(Path(first["directory"])) == before


@pytest.mark.parametrize("mode", ["native", "add-margins", "match-series"])
@pytest.mark.parametrize(
    "failure", ["expected-source", "expected-manifest", "unaccepted", "saved-alpha", "saved-weight"]
)
def test_intact_delivery_cannot_bypass_current_authorization_or_operands(
    tmp_path, monkeypatch, mode, failure
):
    import hashlib

    project, _, selected = protected_project(tmp_path)
    arguments = mode_arguments(mode)
    output = export_project(project, **arguments)
    directory = Path(output["directory"])
    before = hashes(directory)
    state = read_project(project)
    manifest = project / "revisions" / selected["revision"] / "manifest.json"
    if failure.startswith("expected-"):
        arguments.update(
            expected_developed_id=state["developed_id"],
            expected_revision_manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
        )
        arguments[
            "expected_developed_id"
            if failure == "expected-source"
            else "expected_revision_manifest_sha256"
        ] = "0" * 64
    elif failure == "unaccepted":
        state["accepted_revision"] = None
        state["status"] = "review_needed"
        (project / "state.json").write_text(json.dumps(state))
        arguments["revision"] = selected["revision"]
    else:
        from test_ingest import saved_raster

        name = "base_alpha16.png" if failure == "saved-alpha" else "shadow_weight16.png"
        saved_raster(manifest.parent / name).write_bytes(b"Damaged saved operand")
    export = importlib.import_module("blackmask.export")
    monkeypatch.setattr(
        export.tempfile, "mkdtemp", lambda *a, **k: pytest.fail("staged invalid reuse")
    )
    with pytest.raises(ProjectError):
        export_project(project, **arguments)
    assert hashes(directory) == before


@pytest.mark.parametrize("boundary", ["member-hash", "parent-sync"])
def test_intact_reuse_rechecks_raw_source_before_return(tmp_path, monkeypatch, boundary):
    project, _, _ = fixture_project(tmp_path)
    output = export_project(project)
    directory = Path(output["directory"])
    before = hashes(directory)
    export = importlib.import_module("blackmask.export")
    name = "_file_digest" if boundary == "member-hash" else "_sync_directory"
    original = getattr(export, name)
    touched = []

    def change(path):
        value = original(path)
        if not touched and (
            path.parent == directory if boundary == "member-hash" else path == project / "exports"
        ):
            source = project / "source.json"
            source.write_bytes(source.read_bytes() + b" ")
            touched.append(True)
        return value

    monkeypatch.setattr(export, name, change)
    with pytest.raises(ProjectError, match="Stale"):
        export_project(project)
    assert touched and hashes(directory) == before
    assert not list((project / "exports").glob(".export-*"))


@pytest.mark.parametrize(
    "damage", ["missing", "corrupt", "extra", "directory", "symlink", "manifest", "recipe", "fifo"]
)
def test_delivery_members_fail_closed_without_staging(tmp_path, monkeypatch, damage):
    project, _, _ = fixture_project(tmp_path)
    result = export_project(project)
    directory = Path(result["directory"])
    if damage == "missing":
        (directory / "result_RGB8_VIEW.png").rename(tmp_path / "retained-view.png")
    elif damage == "corrupt":
        (directory / "result_RGB8_VIEW.png").write_bytes(b"corrupt")
    elif damage == "extra":
        (directory / ".unexpected").write_text("preserve")
    elif damage == "directory":
        (directory / "extra").mkdir()
    elif damage == "symlink":
        (directory / "result_rgb16.tif").rename(tmp_path / "retained-result.tif")
        (directory / "result_rgb16.tif").symlink_to(tmp_path / "retained-result.tif")
    elif damage == "fifo":
        import os

        os.mkfifo(directory / "unexpected-pipe")
    elif damage == "manifest":
        (directory / "manifest.json").write_bytes((directory / "manifest.json").read_bytes() + b" ")
    else:
        (directory / "recipe.toml").write_text("corrupt")

    def members():
        import os
        import stat

        result = {}
        for path in directory.iterdir():
            info = path.lstat()
            content = (
                path.read_bytes()
                if stat.S_ISREG(info.st_mode)
                else os.readlink(path)
                if stat.S_ISLNK(info.st_mode)
                else None
            )
            result[path.name] = (
                info.st_ino,
                info.st_mode,
                info.st_size,
                info.st_mtime_ns,
                info.st_ctime_ns,
                info.st_nlink,
                content,
            )
        return result

    # Reading can update atime; bytes, identities and modification metadata must remain exact.
    before = members()
    export = importlib.import_module("blackmask.export")
    monkeypatch.setattr(
        export.tempfile, "mkdtemp", lambda *a, **k: pytest.fail("staged damaged reuse")
    )
    with pytest.raises(ProjectError, match="collision"):
        export_project(project)
    assert members() == before


@pytest.mark.parametrize("changed", ["source", "manifest"])
def test_source_change_during_stage_sync_cannot_publish(tmp_path, monkeypatch, changed):
    project, _, selected = fixture_project(tmp_path)
    export = importlib.import_module("blackmask.export")
    path = (
        project / "source.json"
        if changed == "source"
        else project / "revisions" / selected["revision"] / "manifest.json"
    )
    state = (project / "state.json").read_bytes()
    sync = export._sync_directory
    changed_during_sync = []

    def alter_after_stage_sync(directory):
        sync(directory)
        if directory.name.startswith(".export-"):
            path.write_bytes(path.read_bytes() + b" ")
            changed_during_sync.append(True)

    monkeypatch.setattr(export, "_sync_directory", alter_after_stage_sync)
    with pytest.raises(ProjectError, match="Stale"):
        export_project(project)
    assert changed_during_sync and (project / "state.json").read_bytes() == state
    assert not list((project / "exports").glob("rev-*-native-*"))
    assert list((project / "exports").glob(".export-*")), "Failed staged evidence must remain"


def test_actual_export_writer_lock_and_two_process_reuse(tmp_path):
    import select
    import subprocess
    import sys

    project, _, _ = fixture_project(tmp_path)
    before = (project / "state.json").read_bytes()
    records = []
    holder_command = [
        sys.executable,
        "-B",
        "-c",
        "from pathlib import Path;import sys;from blackmask.project import project_lock\nwith project_lock(Path(sys.argv[1])):\n print('locked',flush=True);sys.stdin.readline()",
        str(project),
    ]
    holder = subprocess.Popen(
        holder_command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert holder.stdout is not None and holder.stdin is not None
    try:
        assert select.select([holder.stdout], [], [], 15)[0], (
            "Writer process did not report readiness"
        )
        assert holder.stdout.readline().strip() == "locked"
        command = [sys.executable, "-B", "-m", "blackmask", "export", str(project)]
        busy = subprocess.run(command, capture_output=True, text=True, check=False, timeout=30)
        records.append(
            {
                "command": command,
                "exit": busy.returncode,
                "stdout": busy.stdout,
                "stderr": busy.stderr,
            }
        )
        assert busy.returncode != 0 and "busy" in busy.stderr.lower()
    finally:
        stdout, stderr = holder.communicate("\n", timeout=15)
        records.append(
            {
                "command": holder_command,
                "exit": holder.returncode,
                "stdout": "locked\n" + stdout,
                "stderr": stderr,
            }
        )
    assert holder.returncode == 0
    workers = [
        subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for _ in range(2)
    ]
    outputs = []
    # A busy child's exit does not mean the competing writer has finished.
    completed = [(worker, *worker.communicate(timeout=30)) for worker in workers]
    for worker, stdout, stderr in completed:
        records.append(
            {"command": command, "exit": worker.returncode, "stdout": stdout, "stderr": stderr}
        )
        if worker.returncode:
            assert "busy" in stderr.lower(), stderr
            retry = subprocess.run(command, capture_output=True, text=True, check=False, timeout=30)
            records.append(
                {
                    "command": command,
                    "exit": retry.returncode,
                    "stdout": retry.stdout,
                    "stderr": retry.stderr,
                }
            )
            assert retry.returncode == 0, retry.stderr
            stdout = retry.stdout
        outputs.append(json.loads(stdout))
    (tmp_path / "process-evidence.json").write_text(json.dumps(records, indent=2))
    assert outputs[0]["directory"] == outputs[1]["directory"]
    assert len(list((project / "exports").glob("rev-*-native-*"))) == 1
    assert not list((project / "exports").glob(".export-*"))
    assert (project / "state.json").read_bytes() == before


@pytest.mark.parametrize("mode", ["native", "add-margins", "match-series"])
@pytest.mark.parametrize("with_spatial", [False, True])
def test_requested_export_reconstructs_in_fresh_process(tmp_path, mode, with_spatial):
    import os
    import shutil
    import subprocess
    import sys

    from blackmask.framing import save_framing_preset
    from blackmask.operations import apply_operation
    from blackmask.series_framing import save_series_settings

    project, _, _ = protected_project(tmp_path)
    selected = {}
    if with_spatial:
        from test_spatial_fade import spatial_request

        spatial = apply_operation(project, spatial_request(project))
        selected = {"revision": spatial["revision"], "draft": True}
    result = export_project(
        project, variants=("black", "transparent", "editable"), **selected, **mode_arguments(mode)
    )
    reference = Path(result["directory"])
    frozen = json.loads((reference / "manifest.json").read_bytes())
    # Change the working result as well as both presets; replay must use the selected saved revision.
    from test_background import background_request

    newer = apply_operation(project, background_request(project, "#123456", 0.2))
    assert newer["revision"] != result["revision"]
    copy = tmp_path / "reconstruction"
    shutil.copytree(project, copy, ignore=shutil.ignore_patterns("exports", "cache"))
    source = tmp_path / "source.tif"
    source.rename(tmp_path / "retained-source.tif")
    relative_reference = reference.relative_to(project)
    disconnected = tmp_path / "unavailable-original-project"
    project.rename(disconnected)
    reference = disconnected / relative_reference
    assert (
        not project.exists() and not (copy / "exports").exists() and not (copy / "cache").exists()
    )
    save_framing_preset(
        copy,
        margins(7, 6, 5, 4),
        expected_digest=None,
        expected_developed_id=read_project(copy)["developed_id"],
    )
    changed = mode_arguments("match-series")["series"] | {"name": "Changed", "output_width_px": 61}
    save_series_settings(
        copy,
        changed,
        expected_digest=None,
        expected_developed_id=read_project(copy)["developed_id"],
    )
    program = """import importlib,json,socket,sys
from pathlib import Path
from unittest.mock import patch
from blackmask.export import export_project
record=json.loads(sys.argv[2])
module=importlib.import_module({'native':'blackmask.export','add-margins':'blackmask.framing','match-series':'blackmask.series_framing'}[record['mode']])
name={'native':'render_background','add-margins':'frame_result','match-series':'render_series'}[record['mode']]
arguments={'variants':tuple(record['requested_variants']),'revision':record['revision'],'draft':record['draft']}
if record['mode']=='add-margins': arguments['framing']=record['margins']
if record['mode']=='match-series': arguments['series']=record['settings']
with patch.object(socket,'socket',side_effect=AssertionError('offline')),patch.object(module,name,wraps=getattr(module,name)) as render:
    output=export_project(Path(sys.argv[1]),**arguments)
    assert render.call_count>0 and output['reused'] is False
print(json.dumps({'output':output,'render_calls':render.call_count,'import':importlib.import_module('blackmask.export').__file__}))
"""
    completed = subprocess.run(
        [sys.executable, "-B", "-c", program, str(copy), json.dumps(frozen)],
        check=False,
        capture_output=True,
        text=True,
        env=dict(
            os.environ,
            BLACKMASK_SAM_CACHE=str(tmp_path / "absent-models"),
            BLACKMASK_VITMATTE_CACHE=str(tmp_path / "absent-models"),
        ),
        timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    output = json.loads(completed.stdout)
    regenerated = Path(output["output"]["directory"])
    for name in ("result_rgb16.tif", "black_rgb16.tif"):
        np.testing.assert_array_equal(
            tifffile.imread(reference / name), tifffile.imread(regenerated / name)
        )
    for name in ("result_RGB8_VIEW.png", "black_RGB8_VIEW.png", "transparent_RGBA8_VIEW.png"):
        with Image.open(reference / name) as first, Image.open(regenerated / name) as second:
            np.testing.assert_array_equal(np.array(first), np.array(second))
            assert (
                first.mode == second.mode
                and first.info["icc_profile"] == second.info["icc_profile"] == srgb_profile()
            )
    assert (reference / "manifest.json").read_bytes() == (
        regenerated / "manifest.json"
    ).read_bytes()
