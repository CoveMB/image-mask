"""Series presentation contracts, using synthetic data and independent geometry."""

import hashlib
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import tifffile
from PIL import Image

import blackmask.series_framing as series
from blackmask.series_framing import (
    SeriesSettings,
    compute_series_layout,
    estimate_series_resources,
    parse_series_preset,
    portable_series_preset,
    read_series_preset_file,
    render_series,
    series_sampling_plan,
    validate_series_settings,
)


def series_settings(**changes):
    values = {
        "name": "Portrait series",
        "output_width_px": 4000,
        "output_height_px": 5000,
        "side_margin_tenths_percent": 150,
        "minimum_vertical_margin_tenths_percent": 50,
    }
    values.update(changes)
    return validate_series_settings(values)


def test_series_settings_strict_portable_round_trip(tmp_path):
    settings = series_settings(name="Été 🦋 <series>")
    raw = portable_series_preset(settings)
    value = json.loads(raw)
    assert value == {
        "schema_version": 1,
        "kind": "series-framing-preset",
        "name": "Été 🦋 <series>",
        "output_width_px": 4000,
        "output_height_px": 5000,
        "side_margin_tenths_percent": 150,
        "minimum_vertical_margin_tenths_percent": 50,
    }
    path = tmp_path / "preset.json"
    path.write_bytes(raw)
    assert parse_series_preset(raw) == read_series_preset_file(path) == settings
    assert isinstance(settings, SeriesSettings)


@pytest.mark.parametrize(
    "changes",
    [
        {"name": " "},
        {"name": "x" * 81},
        {"output_width_px": True},
        {"output_height_px": 0},
        {"output_width_px": 32769},
        {"output_width_px": 10001, "output_height_px": 10000},
        {"side_margin_tenths_percent": 150.0},
        {"minimum_vertical_margin_tenths_percent": -1},
        {"side_margin_tenths_percent": 451},
        {"extra": 1},
    ],
)
def test_series_settings_rejects_invalid_values(changes):
    with pytest.raises(ValueError):
        series_settings(**changes)


def test_series_settings_rejects_ambiguous_json_and_unsafe_files(tmp_path):
    raw = portable_series_preset(series_settings())
    for bad in (
        raw.replace(b'"schema_version":1', b'"schema_version":true'),
        raw.replace(b'"schema_version":1', b'"schema_version":2'),
        raw.replace(b'"name":', b'"name":"other","name":'),
        raw.replace(b'"side_margin_tenths_percent":150', b'"side_margin_tenths_percent":NaN'),
        b" " * 16385,
        b"\xff",
        b"[]",
    ):
        with pytest.raises(ValueError):
            parse_series_preset(bad)
    path = tmp_path / "preset.json"
    path.write_bytes(raw)
    alias = tmp_path / "alias.json"
    alias.symlink_to(path)
    for unsafe in (alias, tmp_path, tmp_path / "missing"):
        with pytest.raises((ValueError, OSError)):
            read_series_preset_file(unsafe)
    assert path.read_bytes() == raw


def test_series_layout_width_height_and_fractional_geometry():
    horizontal = compute_series_layout(
        np.full((1, 10000), 65535, np.uint16),
        series_settings(output_height_px=5001, side_margin_tenths_percent=0),
    )
    assert horizontal.scale == pytest.approx(0.4)
    assert horizontal.transformed_subject_bounds_xyxy == pytest.approx((0, 2500.3, 4000, 2500.7))
    assert horizontal.fit_reason == "side-margins-matched"
    tall = compute_series_layout(
        np.full((10000, 1), 65535, np.uint16), series_settings(output_height_px=5001)
    )
    assert tall.geometric_margins_lrtb_px[2:] == pytest.approx((250.05, 250.05))
    assert tall.fit_reason == "height-limited"
    assert all(np.isfinite(value) for value in tall.translation_xy)


def test_series_layout_all_positive_alpha_and_empty_mask():
    alpha = np.zeros((20, 30), np.uint16)
    alpha[5:12, 10:20] = 26214
    alpha[1, 2] = 1
    before = alpha.tobytes()
    layout = compute_series_layout(alpha, series_settings())
    assert layout.subject_bounds_xyxy == (2, 1, 20, 12)
    assert layout.source_edge_contact is False
    alpha[0, 29] = 1
    assert compute_series_layout(alpha, series_settings()).source_edge_contact is True
    assert before != alpha.tobytes()  # fixture really includes the added edge tip
    for invalid in (
        np.zeros((2, 3), np.uint16),
        np.ones((2, 3), np.uint8),
        np.ones((2, 3, 1), np.uint16),
    ):
        with pytest.raises(ValueError):
            compute_series_layout(invalid, series_settings())


def scalar_weights(center, spacing):
    """Independent infinite-zero-lattice Lanczos weights, in float64."""
    radius = 3 * max(1.0, spacing)
    indices = np.arange(int(np.floor(center - radius)) - 1, int(np.ceil(center + radius)) + 1)
    z = (indices + 0.5 - center) / max(1.0, spacing)
    weights = np.where(np.abs(z) < 3, np.sinc(z) * np.sinc(z / 3), 0)
    return indices, weights / weights.sum()


def scalar_matrices(sampling, *, effective):
    axes = []
    for axis in (sampling.x, sampling.y):
        if effective:
            start, stop = (float(np.float32(x)) for x in axis.box)
            spacing = float(np.float32(stop - start)) / axis.output_length
            centers = [
                start + (i + 0.5) * spacing + axis.padding_origin for i in range(axis.output_length)
            ]
        else:
            spacing = axis.spacing
            centers = [axis.ideal_start + (i + 0.5) * spacing for i in range(axis.output_length)]
        matrix = np.zeros((axis.output_length, axis.core_length), np.float64)
        for row, center in enumerate(centers):
            indices, weights = scalar_weights(center, spacing)
            inside = (indices >= 0) & (indices < axis.core_length)
            matrix[row, indices[inside]] = weights[inside]
        axes.append(matrix)
    return axes


def scalar_sample(core, sampling, *, effective):
    x, y = scalar_matrices(sampling, effective=effective)
    return y @ core @ x.T


def sampled_plane(foreground, alpha, sampling, plane, weight=None, opacity=0):
    result = np.empty((sampling.y.output_length, sampling.x.output_length), np.float32)
    for rows, columns, values in series._plane_tiles(
        foreground, alpha, sampling, plane, weight, opacity
    ):
        result[rows, columns] = values
    return result


@pytest.mark.parametrize(
    "shape,output",
    [
        ((4, 7), (19, 17)),
        ((9, 12), (7, 11)),
        ((1, 8), (13, 15)),
        ((8, 1), (15, 13)),
        ((83, 5), (17, 23)),
        ((5, 83), (23, 17)),
    ],
)
def test_series_sampling_scalar_oracles_and_phase(shape, output):
    alpha = np.full(shape, 26214, np.uint16)
    alpha.flat[0] = 1
    foreground = (np.arange(alpha.size * 3).reshape((*shape, 3)) * 293 + 117).astype(np.uint16)
    weight = np.full(shape, 19001, np.uint16)
    layout = compute_series_layout(
        alpha, series_settings(output_width_px=output[0], output_height_px=output[1])
    )
    sampling = series_sampling_plan(layout)
    for axis in (sampling.x, sampling.y):
        assert axis.maximum_output_phase_error <= 1 / 64
    for plane in (-1, 0, 1, 2):
        core = alpha.astype(np.float64) / 65535
        if plane >= 0:
            core *= foreground[..., plane] * (1 - 0.37 * weight.astype(np.float64) / 65535)
        actual = sampled_plane(foreground, alpha, sampling, plane, weight, 0.37)
        effective = scalar_sample(core, sampling, effective=True)
        ideal = scalar_sample(core, sampling, effective=False)
        tolerance = 2e-6 if plane == -1 else 0.125
        np.testing.assert_allclose(actual, effective, rtol=0, atol=tolerance)
        xi, yi = scalar_matrices(sampling, effective=False)
        xf, yf = scalar_matrices(sampling, effective=True)
        coefficient_bound = np.max(np.abs(core)) * (
            np.abs(yf).sum(axis=1)[:, None] * np.abs(xf - xi).sum(axis=1)[None, :]
            + np.abs(yf - yi).sum(axis=1)[:, None] * np.abs(xi).sum(axis=1)[None, :]
        )
        assert np.all(np.abs(ideal - effective) <= coefficient_bound + 1e-10)
        assert np.all(np.abs(actual - ideal) <= coefficient_bound + tolerance)
        print(
            json.dumps(
                {
                    "shape": shape,
                    "output": output,
                    "plane": plane,
                    "arithmetic_max_error": float(np.max(np.abs(actual - effective))),
                    "ideal_effective_max_difference": float(np.max(np.abs(ideal - effective))),
                    "maximum_output_phase_error": max(
                        sampling.x.maximum_output_phase_error, sampling.y.maximum_output_phase_error
                    ),
                }
            )
        )


def test_series_sampling_zero_extended_edges_singletons_and_identity():
    alpha = np.zeros((9, 12), np.uint16)
    alpha[0, 11] = 26214
    foreground = np.full((9, 12, 3), [137, 30001, 65003], np.uint16)
    settings = series_settings(
        output_width_px=47,
        output_height_px=49,
        side_margin_tenths_percent=450,
        minimum_vertical_margin_tenths_percent=450,
    )
    sampling = series_sampling_plan(compute_series_layout(alpha, settings))
    actual = sampled_plane(foreground, alpha, sampling, -1)
    reference = scalar_sample(np.array([[0.4]]), sampling, effective=True)
    np.testing.assert_allclose(actual, reference, rtol=0, atol=2e-6)
    assert actual.min() < 0
    rgba = render_series(foreground, alpha, sampling, transparent=True)
    assert not rgba[rgba[..., 3] == 0, :3].any()
    identity_alpha = np.array([[1, 26214], [65535, 32767]], np.uint16)
    identity_rgb = np.array([[[117, 10001, 65003]] * 2] * 2, np.uint16)
    identity = series_sampling_plan(
        compute_series_layout(
            identity_alpha,
            series_settings(
                output_width_px=2,
                output_height_px=2,
                side_margin_tenths_percent=0,
                minimum_vertical_margin_tenths_percent=0,
            ),
        )
    )
    expected = np.rint(
        identity_rgb.astype(np.float64) * (identity_alpha.astype(np.float64) / 65535)[..., None]
    ).astype(np.uint16)
    np.testing.assert_array_equal(render_series(identity_rgb, identity_alpha, identity), expected)
    shifted = np.zeros((100, 32000), np.uint16)
    shifted[90:94, 31000:31007] = 26214
    shifted_plan = series_sampling_plan(compute_series_layout(shifted, settings))
    assert max(shifted_plan.x.box) < 100
    assert shifted_plan.x.maximum_output_phase_error <= 1 / 64


def test_series_sampling_bounds_alpha_and_rgba():
    alpha = np.zeros((4, 6), np.uint16)
    alpha[1:3, 1:5] = [[1, 26214, 65535, 32768], [65535, 1, 26214, 65535]]
    foreground = np.full((4, 6, 3), [65003, 10001, 117], np.uint16)
    sampling = series_sampling_plan(
        compute_series_layout(alpha, series_settings(output_width_px=19, output_height_px=21))
    )
    rgba = render_series(foreground, alpha, sampling, transparent=True)
    composed = render_series(
        foreground, alpha, sampling, background_settings={"color_srgb": "#315579", "variation": 0}
    )
    assert rgba.shape == (21, 19, 4) and composed.dtype == np.uint16
    assert not rgba[rgba[..., 3] == 0, :3].any()
    before = foreground.copy()
    foreground[alpha == 0] = [0, 65535, 65535]
    np.testing.assert_array_equal(
        render_series(foreground, alpha, sampling, transparent=True), rgba
    )
    np.testing.assert_array_equal(
        render_series(
            foreground,
            alpha,
            sampling,
            background_settings={"color_srgb": "#315579", "variation": 0},
        ),
        composed,
    )
    assert np.any(before[alpha != 0] % 257)


def test_series_resource_estimate_precedes_large_allocation():
    alpha = np.ones((3, 5), np.uint16)
    sampling = series_sampling_plan(
        compute_series_layout(alpha, series_settings(output_width_px=4000, output_height_px=5000))
    )
    estimate = estimate_series_resources(sampling, retained_native_bytes=40, transparent=True)
    assert estimate["output_rgb16_bytes"] == 120_000_000
    assert estimate["retained_native_bytes"] == 40
    assert estimate["scalar_intermediate_bytes"] > 0
    assert estimate["estimated_peak_bytes"] >= 120_000_040
    from dataclasses import replace

    huge = replace(sampling.layout, subject_bounds_xyxy=(0, 0, 10**15, 1), scale=1e-15)
    with pytest.raises(ValueError, match="sampling|Pillow|coefficient"):
        series_sampling_plan(huge)


def test_series_sampling_transparent_quantization_keeps_scratch_bounded(monkeypatch):
    alpha = np.full((5, 7), 26214, np.uint16)
    foreground = np.full((5, 7, 3), 30001, np.uint16)
    sampling = series_sampling_plan(
        compute_series_layout(alpha, series_settings(output_width_px=211, output_height_px=217))
    )
    original = np.rint

    def bounded_round(values, *args, **kwargs):
        if values.ndim == 2:
            assert min(values.shape) <= 64
        return original(values, *args, **kwargs)

    monkeypatch.setattr(np, "rint", bounded_round)
    assert render_series(foreground, alpha, sampling, transparent=True).shape == (217, 211, 4)


def test_series_export_round_trip_identity_and_preservation(tmp_path):
    from test_framing import hashes, protected_project

    from blackmask.export import export_project
    from blackmask.ingest import srgb_profile

    project, _, _ = protected_project(tmp_path)
    export_project(project)
    export_project(project, framing={"left_px": 0, "right_px": 0, "top_px": 0, "bottom_px": 0})
    before = hashes(project)
    settings = series_settings(output_width_px=40, output_height_px=50).to_dict()
    output = export_project(project, series=settings, framed_transparent=True)
    directory = Path(output["directory"])
    record = json.loads(Path(output["manifest_file"]).read_bytes())
    assert record["kind"] == "series-framed-presentation"
    assert (
        record["source_record_sha256"]
        == hashlib.sha256((project / "source.json").read_bytes()).hexdigest()
    )
    assert record["settings"] == settings
    assert output["output_dimensions_wh"] == [40, 50]
    pixels = tifffile.imread(directory / "result_rgb16.tif")
    assert pixels.shape == (50, 40, 3) and pixels.dtype == np.uint16
    assert np.any(pixels % 257)
    with Image.open(directory / "transparent_RGBA8_VIEW.png") as image:
        rgba = np.array(image)
        assert image.info["icc_profile"] == srgb_profile()
    assert not rgba[rgba[..., 3] == 0, :3].any()
    assert "resized presentation" in (directory / "README.txt").read_text()
    assert not any(text in json.dumps(record) for text in (str(tmp_path), "/Users/", "source.tif"))
    first = hashes(project)
    assert export_project(project, series=settings, framed_transparent=True) == output
    assert hashes(project) == first
    assert not list((project / "exports").glob(".export-*"))
    assert all(hashes(project)[name] == value for name, value in before.items())
    drafted = export_project(project, series=settings, revision=output["revision"], draft=True)
    assert json.loads(Path(drafted["manifest_file"]).read_bytes())["draft"] is True


def test_series_export_selected_revision_expected_identity(tmp_path):
    from test_effects import shading_request
    from test_framing import protected_project

    from blackmask import operations
    from blackmask.export import export_project
    from blackmask.project import read_project

    project, _, accepted = protected_project(tmp_path)
    selected = operations.apply_operation(project, shading_request(project, opacity=0.12))[
        "revision"
    ]
    working = operations.apply_operation(project, shading_request(project, opacity=0.22))[
        "revision"
    ]
    assert len({accepted["revision"], selected, working}) == 3
    master = read_project(project)["master_id"]
    expected = hashlib.sha256(
        (project / "revisions" / selected / "manifest.json").read_bytes()
    ).hexdigest()
    settings = series_settings(output_width_px=40, output_height_px=50).to_dict()
    output = export_project(
        project,
        series=settings,
        revision=selected,
        draft=True,
        expected_master_id=master,
        expected_revision_manifest_sha256=expected,
    )
    assert output["revision"] == selected
    for changes in (
        {"expected_master_id": "0" * 64},
        {"expected_revision_manifest_sha256": "0" * 64},
        {"expected_master_id": None},
    ):
        arguments = {
            "series": settings,
            "revision": selected,
            "draft": True,
            "expected_master_id": master,
            "expected_revision_manifest_sha256": expected,
        }
        arguments.update(changes)
        with pytest.raises(ValueError):
            export_project(project, **arguments)
    with pytest.raises(ValueError, match="Unaccepted"):
        export_project(project, series=settings, revision=selected)


@pytest.mark.parametrize(
    "failure", ["mismatch", "sync", "cleanup", "readback", "disk", "estimate", "state-change"]
)
def test_series_export_failures_reuse_and_recovery(tmp_path, monkeypatch, failure):
    from test_framing import hashes, protected_project

    from blackmask.export import export_project

    export = importlib.import_module("blackmask.export")
    project, _, _ = protected_project(tmp_path)
    settings = series_settings(output_width_px=40, output_height_px=50).to_dict()
    output = Path(export_project(project, series=settings)["directory"])
    retained = project / "exports" / ".export-earlier-failure"
    retained.mkdir()
    (retained / "evidence.txt").write_text("preserved")
    if failure == "mismatch":
        note = output / "README.txt"
        raw = note.read_bytes()
        note.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
    before = hashes(project)
    if failure == "sync":
        original = export._sync_directory

        def sync(path):
            if path == project / "exports":
                raise OSError("injected parent sync")
            original(path)

        monkeypatch.setattr(export, "_sync_directory", sync)
    elif failure == "cleanup":

        def cleanup(path):
            (path / "README.txt").unlink()
            raise OSError("injected partial cleanup")

        monkeypatch.setattr(export.shutil, "rmtree", cleanup)
    elif failure == "readback":
        monkeypatch.setattr(
            export,
            "_verify_framed_png",
            lambda *args: (_ for _ in ()).throw(ValueError("injected roundtrip failure")),
        )
    elif failure == "disk":
        monkeypatch.setattr(
            export,
            "check_space",
            lambda *args: (_ for _ in ()).throw(ValueError("injected disk refusal")),
        )
    elif failure == "estimate":
        monkeypatch.setattr(
            series,
            "estimate_series_resources",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                ValueError("injected allocation refusal")
            ),
        )
    elif failure == "state-change":
        original_render = series.render_series

        def changed(*args, **kwargs):
            pixels = original_render(*args, **kwargs)
            path = project / "state.json"
            path.write_bytes(path.read_bytes() + b"\n")
            return pixels

        monkeypatch.setattr(series, "render_series", changed)
    with pytest.raises((ValueError, OSError)) as error:
        export_project(project, series=settings)
    if failure == "cleanup":
        assert "durably published" in str(error.value) and "cleanup failed" in str(error.value)
    after = hashes(project)
    assert all(
        after[name] == value
        for name, value in before.items()
        if not (failure == "state-change" and name == "state.json")
    )
    assert (retained / "evidence.txt").read_text() == "preserved"
    if failure in {"disk", "estimate"}:
        assert list((project / "exports").glob(".export-*")) == [retained]


def test_series_settings_save_raw_cas_and_native_preservation(tmp_path):
    from test_framing import hashes, protected_project

    from blackmask.project import read_project

    project, _, _ = protected_project(tmp_path)
    source_id = read_project(project)["master_id"]
    settings, digest = series.read_series_settings(project, source_id, (6, 4))
    assert settings == SeriesSettings() and digest is None
    assert not (project / "series-framing.json").exists()
    before = hashes(project)
    saved = series.save_series_settings(
        project,
        series_settings(output_width_px=40, output_height_px=50).to_dict(),
        expected_digest=None,
        expected_source_id=source_id,
    )
    path = project / "series-framing.json"
    raw = path.read_bytes()
    assert saved["series_digest"] == hashlib.sha256(raw).hexdigest()
    assert set(json.loads(raw)) == {
        "schema_version",
        "master_id",
        "source_dimensions_wh",
        "settings",
    }
    assert (
        series.save_series_settings(
            project,
            saved["series_settings"],
            expected_digest=saved["series_digest"],
            expected_source_id=source_id,
        )
        == saved
    )
    assert path.read_bytes() == raw
    path.write_bytes(raw + b"\n")
    with pytest.raises(ValueError, match="Stale"):
        series.save_series_settings(
            project,
            saved["series_settings"],
            expected_digest=saved["series_digest"],
            expected_source_id=source_id,
        )
    for bad in (
        b" " * 16385,
        raw.replace(b'"schema_version":1', b'"schema_version":true'),
        raw.replace(source_id.encode(), b"0" * 64),
        raw.replace(b'"settings":', b'"extra":1,"settings":'),
    ):
        path.write_bytes(bad)
        with pytest.raises(ValueError):
            series.read_series_settings(project, source_id, (6, 4))
        assert path.read_bytes() == bad
    after = hashes(project)
    assert all(after[name] == value for name, value in before.items())


def test_series_settings_two_process_lock_and_uncertain_write(tmp_path, monkeypatch):
    from test_framing import protected_project

    from blackmask.project import read_project

    project, _, _ = protected_project(tmp_path)
    source_id = read_project(project)["master_id"]
    saved = series.save_series_settings(
        project, series_settings().to_dict(), expected_digest=None, expected_source_id=source_id
    )
    program = "import json,sys; from pathlib import Path; from blackmask.series_framing import save_series_settings; value=json.loads(sys.argv[4]); save_series_settings(Path(sys.argv[1]),value,expected_digest=sys.argv[2],expected_source_id=sys.argv[3])"
    children = [
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                program,
                str(project),
                saved["series_digest"],
                source_id,
                json.dumps(series_settings(name=name).to_dict()),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=dict(os.environ, PYTHONPATH=str(Path("src").resolve())),
        )
        for name in ("first", "second")
    ]
    results = [(child.communicate(timeout=20), child.returncode) for child in children]
    assert sum(code == 0 for _, code in results) == 1
    assert all(
        code == 0 or b"Stale" in streams[1] or b"busy" in streams[1].lower()
        for streams, code in results
    )
    current, current_digest = series.read_series_settings(project, source_id, (6, 4))
    before = (project / "series-framing.json").read_bytes()
    original_atomic = series._atomic_json
    monkeypatch.setattr(
        series,
        "_atomic_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("before replace")),
    )
    with pytest.raises(ValueError, match="unchanged"):
        series.save_series_settings(
            project,
            series_settings(name="before failure").to_dict(),
            expected_digest=current_digest,
            expected_source_id=source_id,
        )
    assert (project / "series-framing.json").read_bytes() == before
    monkeypatch.setattr(series, "_atomic_json", original_atomic)
    project_module = importlib.import_module("blackmask.project")
    original_sync = project_module._sync_directory

    def fail_sync(path):
        if path == project:
            raise OSError("after replace")
        original_sync(path)

    monkeypatch.setattr(project_module, "_sync_directory", fail_sync)
    with pytest.raises(series.SeriesSaveUncertain) as failure:
        series.save_series_settings(
            project,
            series_settings(name="visible after failure").to_dict(),
            expected_digest=current_digest,
            expected_source_id=source_id,
        )
    assert failure.value.visible["series_reload_required"] is True
    assert failure.value.visible["series_settings"]["name"] == "visible after failure"
    assert (
        failure.value.visible["series_digest"]
        == hashlib.sha256((project / "series-framing.json").read_bytes()).hexdigest()
    )
    assert current.name in {"first", "second"}


def series_project(tmp_path, shape=(4, 9)):
    from test_ingest import tiff
    from test_matte_operations import approve, run_matte
    from test_operations import edits, request

    from blackmask import operations
    from blackmask.ingest import srgb_profile
    from blackmask.project import accept_development, create_project, read_project

    tmp_path.mkdir(parents=True, exist_ok=True)
    height, width = shape
    pixels = np.full((height, width, 3), [117, 30001, 65003], np.uint16)
    project = tmp_path / "project"
    create_project(tiff(tmp_path / "source.tif", pixels, profile=srgb_profile()), project, {})
    accept_development(project, read_project(project)["master_id"])
    name = edits(
        project,
        [
            {"id": "bg", "role": "background", "shape": "rectangle", "xyxy": [0, 0, 1, height]},
            {
                "id": "fg",
                "role": "foreground",
                "shape": "rectangle",
                "xyxy": [width - 1, 0, width, height],
            },
        ],
    )
    prepared = operations.apply_operation(project, request(project, guide_edits_file=name))
    approve(project, prepared)
    result = run_matte(project)
    operations.accept_revision(project, result["revision"])
    return project


def test_series_portable_reuse_two_photos_independent_snapshots(tmp_path):
    from blackmask.export import export_project
    from blackmask.project import read_project

    first, second = (
        series_project(tmp_path / "long", (4, 9)),
        series_project(tmp_path / "tall", (9, 4)),
    )
    raw = portable_series_preset(series_settings(output_width_px=40, output_height_px=50))
    settings = parse_series_preset(raw)
    outputs, presets = [], []
    for project in (first, second):
        source_id = read_project(project)["master_id"]
        series.save_series_settings(
            project, settings.to_dict(), expected_digest=None, expected_source_id=source_id
        )
        presets.append((project / "series-framing.json").read_bytes())
        outputs.append(export_project(project, series=settings.to_dict()))
    assert outputs[0]["output_dimensions_wh"] == outputs[1]["output_dimensions_wh"] == [40, 50]
    assert (
        outputs[0]["layout"]["subject_bounds_xyxy"] != outputs[1]["layout"]["subject_bounds_xyxy"]
    )
    portable_series_preset(
        series_settings(name="Later external preset", output_width_px=60, output_height_px=70)
    )
    assert [
        (project / "series-framing.json").read_bytes() for project in (first, second)
    ] == presets
