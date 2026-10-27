"""Portable appearance boundaries, using independent synthetic expectations."""

import base64
import copy
import importlib
import io
import json
import math
import struct
import zlib

import numpy as np
import pytest
from PIL import Image, PngImagePlugin


def appearance_module():
    return importlib.import_module("blackmask.appearance_recipes")


def recipe_value(**sections):
    return {
        "schema_version": 1,
        "kind": "appearance-recipe",
        "name": "<img> local look",
        "sections": sections or {"shadow_fade": {"amount": 0.4, "preserve_highlights": 0.7}},
        "reference": None,
    }


def recipe_bytes(value):
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def reference_value(raw=None, *, size=(4, 3), mode="RGB"):
    if raw is None:
        stream = io.BytesIO()
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("private", "private source identity")
        Image.new(mode, size).save(stream, format="PNG", pnginfo=metadata)
        raw = stream.getvalue()
    return {
        "mime": "image/png",
        "width": size[0],
        "height": size[1],
        "png_base64": base64.b64encode(raw).decode("ascii"),
    }


@pytest.mark.parametrize(
    "sections",
    [
        {"shadow_fade": {"amount": 0.4, "preserve_highlights": 0.7}},
        {"local_exposure": {"ev": -1.25}},
        {"color_cleanup": {"strength": 0.3}},
        {"background": {"color_srgb": "#AB12EF", "variation": 0.125}},
        {"shading": {"width_subject_fraction": 0.0125, "direction_degrees": 37, "opacity": 0.4}},
        {
            "spatial_fade": {
                "transition_subject_fraction": 0.005,
                "amount": 0.6,
                "preserve_highlights": 0.2,
            }
        },
        {
            "shadow_fade": {"amount": 0.4, "preserve_highlights": 0.7},
            "local_exposure": {"ev": 1.25},
            "background": {"color_srgb": "#000000", "variation": 0},
        },
    ],
)
def test_appearance_recipe_strict_roundtrip(sections):
    recipes = appearance_module()
    value = recipe_value(**sections)
    assert recipes.parse_appearance_recipe(recipes.portable_appearance_recipe(value)) == value
    assert set(json.loads(recipes.portable_appearance_recipe(value))) == {
        "schema_version",
        "kind",
        "name",
        "sections",
        "reference",
    }


@pytest.mark.parametrize(
    "change",
    [
        {"schema_version": True},
        {"schema_version": 2},
        {"kind": "other"},
        {"name": ""},
        {"name": "x" * 81},
        {"name": "bad\nname"},
        {"name": "\ud800"},
        {"project": "private"},
        {"sections": {}},
        {"sections": {"source": {}}},
        {"sections": {"shadow_fade": {"amount": True, "preserve_highlights": 0}}},
        {"sections": {"shadow_fade": {"amount": 1.01, "preserve_highlights": 0}}},
        {"sections": {"shadow_fade": {"amount": 0, "preserve_highlights": 0, "enabled": True}}},
        {"sections": {"local_exposure": {"ev": 3.01}}},
        {"sections": {"color_cleanup": {"strength": -0.01}}},
        {"sections": {"background": {"color_srgb": "red", "variation": 0}}},
        {
            "sections": {
                "shading": {"width_subject_fraction": 0, "direction_degrees": 0, "opacity": 1}
            }
        },
        {
            "sections": {
                "spatial_fade": {
                    "transition_subject_fraction": -1,
                    "amount": 0,
                    "preserve_highlights": 0,
                }
            }
        },
    ],
)
def test_portable_rejects_invalid_or_private_fields(change):
    value = recipe_value()
    value.update(change)
    with pytest.raises(ValueError):
        appearance_module().portable_appearance_recipe(value)


@pytest.mark.parametrize(
    "fragment,replacement",
    [
        (
            b'"kind": "appearance-recipe"',
            b'"kind": "appearance-recipe", "kind": "appearance-recipe"',
        ),
        (b'"amount": 0.4', b'"amount": 0.4, "amount": 0.4'),
    ],
)
def test_import_rejects_duplicate_keys_in_otherwise_valid_recipe(fragment, replacement):
    recipes = appearance_module()
    value = recipe_value()
    raw = recipe_bytes(value)
    assert recipes.parse_appearance_recipe(raw) == value
    assert fragment in raw
    with pytest.raises(ValueError, match="Duplicate appearance recipe JSON key"):
        recipes.parse_appearance_recipe(raw.replace(fragment, replacement, 1))


@pytest.mark.parametrize("number", [b"NaN", b"Infinity", b"-Infinity", b"1e999"])
def test_import_rejects_nonfinite_section_numbers(number):
    raw = recipe_bytes(recipe_value()).replace(b'"amount": 0.4', b'"amount": ' + number)
    with pytest.raises(ValueError, match="finite"):
        appearance_module().parse_appearance_recipe(raw)


def test_import_checks_nesting_before_decoding_and_ignores_quoted_brackets(monkeypatch):
    recipes = appearance_module()
    value = recipe_value()
    value["name"] = '[[[[[[[[[ { \\"quoted\\" } ]]]]]]]]]'
    assert recipes.parse_appearance_recipe(recipe_bytes(value)) == value
    # Root plus seven nested arrays reaches eight; ordinary name validation owns it.
    raw = recipe_bytes(recipe_value()).replace(b'"<img> local look"', b"[" * 7 + b"0" + b"]" * 7)
    with pytest.raises(ValueError, match="name must be text"):
        recipes.parse_appearance_recipe(raw)

    def forbidden_decoder(*args, **kwargs):
        raise AssertionError("Over-depth input reached the JSON decoder")

    monkeypatch.setattr(recipes.json, "loads", forbidden_decoder)
    raw = recipe_bytes(recipe_value()).replace(b'"<img> local look"', b"[" * 8 + b"0" + b"]" * 8)
    with pytest.raises(ValueError, match="nesting exceeds 8 levels"):
        recipes.parse_appearance_recipe(raw)


def test_import_rejects_invalid_utf8():
    with pytest.raises(ValueError, match="UTF-8 JSON"):
        appearance_module().parse_appearance_recipe(b"\xff")


def test_json_byte_limit_counts_encoded_utf8_and_reference():
    recipes = appearance_module()
    value = recipe_value()
    value["name"] = "  Café 🐉  "
    value["reference"] = reference_value()
    raw = recipe_bytes(value)
    raw += b" " * (1572864 - len(raw))
    assert recipes.parse_appearance_recipe(raw)["name"] == "Café 🐉"
    with pytest.raises(ValueError):
        recipes.parse_appearance_recipe(raw + b" ")


def test_shading_and_spatial_are_mutually_exclusive():
    with pytest.raises(ValueError):
        appearance_module().portable_appearance_recipe(
            recipe_value(
                shading={"width_subject_fraction": 0.1, "direction_degrees": 0, "opacity": 0.5},
                spatial_fade={
                    "transition_subject_fraction": 0.1,
                    "amount": 0.5,
                    "preserve_highlights": 0.5,
                },
            )
        )


def test_fractional_width_conversion_includes_faint_bounds():
    from blackmask import series_framing

    recipes = appearance_module()
    alpha = np.zeros((90, 120), np.uint16)
    alpha[10:70, 20:90] = 65535
    alpha[5, 10] = alpha[84, 109] = 1
    bounds = series_framing.nonzero_alpha_bounds(alpha)
    assert bounds == (10, 5, 110, 85)
    value = recipe_value(
        spatial_fade={
            "transition_subject_fraction": 0.005,
            "amount": 0.6,
            "preserve_highlights": 0.2,
        }
    )
    result = recipes.appearance_recipe_form_values(value, bounds, (120, 90))
    assert result == {
        "sections": {
            "spatial_fade": {"transition_width": 0.5, "amount": 0.6, "preserve_highlights": 0.2}
        },
        "unavailable": {},
    }
    doubled = recipes.appearance_recipe_form_values(value, (20, 10, 220, 170), (240, 180))
    assert doubled["sections"]["spatial_fade"]["transition_width"] == 1
    shading = recipe_value(
        shading={"width_subject_fraction": 0.0125, "direction_degrees": 37, "opacity": 0.4}
    )
    assert (
        recipes.appearance_recipe_form_values(shading, bounds, (120, 90))["sections"]["shading"][
            "width_px"
        ]
        == 1.25
    )
    assert series_framing.nonzero_alpha_bounds(np.zeros((4, 5), np.uint16)) is None


def test_width_conversion_keeps_independent_sections_and_native_shading_limit():
    recipes = appearance_module()
    value = recipe_value(
        shading={"width_subject_fraction": 3, "direction_degrees": 37, "opacity": 0.4},
        local_exposure={"ev": 1.25},
    )
    original = copy.deepcopy(value)
    result = recipes.appearance_recipe_form_values(value, (0, 0, 20, 10), (40, 30))
    assert result["sections"] == {"local_exposure": {"ev": 1.25}}
    assert set(result["unavailable"]) == {"shading"}
    assert value == original
    assert recipes.appearance_recipe_form_values(value, None, (40, 30))["sections"] == {
        "local_exposure": {"ev": 1.25}
    }


@pytest.mark.parametrize("kind,endpoint", [("shading", 40.0), ("spatial_fade", 80.0)])
def test_closed_width_endpoint_budget_is_converter_only(kind, endpoint):
    recipes = appearance_module()
    fraction_key = "width_subject_fraction" if kind == "shading" else "transition_subject_fraction"
    width_key = "width_px" if kind == "shading" else "transition_width"
    values = (
        {"direction_degrees": 37, "opacity": 0.4}
        if kind == "shading"
        else {"amount": 0.4, "preserve_highlights": 0.6}
    )
    for width in (1.25, endpoint, math.nextafter(endpoint, math.inf)):
        values[fraction_key] = width
        result = recipes.appearance_recipe_form_values(
            recipe_value(**{kind: values}), (0, 0, 1, 1), (40, 30)
        )
        assert result["sections"][kind][width_key] == min(width, endpoint)
    beyond = endpoint
    for _ in range(10):
        beyond = math.nextafter(beyond, math.inf)
    assert beyond - endpoint > 4 * (math.ulp(beyond) + math.ulp(endpoint))
    values[fraction_key] = beyond
    assert (
        kind
        in recipes.appearance_recipe_form_values(
            recipe_value(**{kind: values}), (0, 0, 1, 1), (40, 30)
        )["unavailable"]
    )


def test_fractional_transition_recovers_only_bounded_roundoff():
    recipes = appearance_module()
    fraction = json.loads(json.dumps(0.5 / 49))
    assert fraction * 49 == 0.49999999999999994
    value = recipe_value(
        spatial_fade={
            "transition_subject_fraction": fraction,
            "amount": 0.4,
            "preserve_highlights": 0.6,
        }
    )
    assert (
        recipes.appearance_recipe_form_values(value, (0, 0, 49, 20), (50, 40))["sections"][
            "spatial_fade"
        ]["transition_width"]
        == 0.5
    )
    value["sections"]["spatial_fade"]["transition_subject_fraction"] = 0.25 / 49
    assert (
        "spatial_fade"
        in recipes.appearance_recipe_form_values(value, (0, 0, 49, 20), (50, 40))["unavailable"]
    )
    from blackmask.spatial_fade import validate_spatial_transition_width

    with pytest.raises(ValueError):
        validate_spatial_transition_width(fraction * 49, 50, 40)


def test_reference_is_sanitized_and_self_contained():
    recipes = appearance_module()
    value = recipe_value()
    value["reference"] = reference_value()
    result = recipes.parse_appearance_recipe(recipe_bytes(value))
    raw = base64.b64decode(result["reference"]["png_base64"])
    assert b"private" not in raw
    with Image.open(io.BytesIO(raw)) as image:
        image.load()
        assert image.mode == "RGB" and image.size == (4, 3)
        assert image.info == {}
        assert image.getpixel((1, 1)) == (0, 0, 0)
    assert recipes.parse_appearance_recipe(recipes.portable_appearance_recipe(result)) == result


@pytest.mark.parametrize(
    "mode,size", [("RGBA", (4, 3)), ("L", (4, 3)), ("RGB", (513, 1)), ("RGB", (512, 513))]
)
def test_reference_rejects_non_rgb8_or_oversized_pixels(mode, size):
    value = recipe_value()
    value["reference"] = reference_value(mode=mode, size=size)
    with pytest.raises(ValueError):
        appearance_module().portable_appearance_recipe(value)


def test_reference_rejects_animation_mismatch_corruption_and_forged_bomb():
    stream = io.BytesIO()
    Image.new("RGB", (4, 3), "red").save(
        stream,
        format="PNG",
        save_all=True,
        append_images=[Image.new("RGB", (4, 3), "blue")],
        duration=10,
    )
    references = [
        reference_value(stream.getvalue()),
        reference_value(b"<svg/>"),
        reference_value(b"x" * 1048577),
    ]
    mismatched = reference_value()
    mismatched["width"] = 5
    references.append(mismatched)
    corrupt = bytearray(base64.b64decode(reference_value()["png_base64"]))
    corrupt[-1] ^= 1
    references.extend([reference_value(bytes(corrupt)), reference_value(bytes(corrupt[:-10]))])
    header = struct.pack(">IIBBBBB", 100000, 100000, 8, 2, 0, 0, 0)
    chunk = b"IHDR" + header
    bomb = (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", len(header))
        + chunk
        + struct.pack(">I", zlib.crc32(chunk))
    )
    references.append(reference_value(bomb))
    for reference in references:
        value = recipe_value()
        value["reference"] = reference
        with pytest.raises(ValueError):
            appearance_module().portable_appearance_recipe(value)


def project_inventory(project):
    from blackmask.project import digest

    return {
        str(path.relative_to(project)): digest(path.read_bytes())
        for path in project.rglob("*")
        if path.is_file()
    }


def test_reference_exact_encoded_and_combined_limits_and_malformed_pixels():
    def chunk(kind, data):
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    raw = base64.b64decode(reference_value(size=(512, 512))["png_base64"])
    padding = chunk(b"tEXt", b"private\0" + b"x" * (1048576 - len(raw) - 20))
    exact = raw[:-12] + padding + raw[-12:]
    assert len(exact) == 1048576
    value = recipe_value()
    value["reference"] = reference_value(exact, size=(512, 512))
    encoded = recipe_bytes(value)
    assert len(encoded) < 1572864
    encoded += b" " * (1572864 - len(encoded))
    sanitized = appearance_module().parse_appearance_recipe(encoded)
    assert b"private" not in base64.b64decode(sanitized["reference"]["png_base64"])
    with pytest.raises(ValueError):
        appearance_module().parse_appearance_recipe(encoded + b" ")
    for invalid in (
        raw[:-12] + chunk(b"tEXt", b"x" * (1048577 - len(raw) - 12)) + raw[-12:],
        raw[:8] + chunk(b"IHDR", struct.pack(">IIBBBBB", 512, 512, 16, 2, 0, 0, 0)) + raw[33:],
        raw[:33] + chunk(b"IDAT", zlib.compress(b"")) + raw[-12:],
        raw[:33] + chunk(b"IDAT", b"invalid compressed pixels") + raw[-12:],
    ):
        value["reference"] = reference_value(invalid, size=(512, 512))
        with pytest.raises(ValueError):
            appearance_module().portable_appearance_recipe(value)


def saved_recipe(project, revision, sections, *, shape=None, reference=False):
    from blackmask.assets import saved_asset
    from blackmask.project import digest

    raw = saved_asset(project, f"revisions/{revision}/manifest.json").read_bytes()
    return appearance_module().appearance_recipe_from_revision(
        project, revision, digest(raw), "Saved source look", sections, shape, reference
    )


@pytest.mark.parametrize("enabled,strength", [(True, 0.8), (False, 0.8), (False, 0)])
def test_recipe_saves_actual_cleanup_record_without_enable_or_identity(tmp_path, enabled, strength):
    from test_background import background_request
    from test_effects import effect_request, fixture_project

    from blackmask import operations

    project, _, _ = fixture_project(tmp_path)
    selected = operations.apply_operation(
        project, effect_request(project, enabled=enabled, strength=strength)
    )
    assert selected["color_cleanup"]["strength"] == strength
    assert "settings" not in selected["color_cleanup"]
    operations.apply_operation(project, background_request(project, "#14283C", 0.125))
    before = project_inventory(project)
    value = json.loads(saved_recipe(project, selected["revision"], ["color_cleanup"]))
    assert value["sections"] == {"color_cleanup": {"strength": strength}}
    assert value["reference"] is None
    assert project_inventory(project) == before


def test_recipe_uses_selected_saved_revision_not_latest_or_draft(tmp_path, monkeypatch):
    import tomllib

    import tomli_w
    from test_background import background_request
    from test_effects import fixture_project
    from test_exposure import exposure_request
    from test_shadow_fade import fade_request

    from blackmask import operations

    project, _, _ = fixture_project(tmp_path)
    operations.apply_operation(project, exposure_request(project, ev=0.5))
    operations.apply_operation(project, fade_request(project, amount=0.25, preserve=0))
    selected = operations.apply_operation(project, background_request(project, "#14283C", 0))
    operations.apply_operation(project, exposure_request(project, ev=-1))
    operations.apply_operation(project, background_request(project, "#884422", 0.125))
    draft = tomllib.loads((project / "recipe.toml").read_text())
    draft["local_exposure"]["ev"] = 2
    (project / "recipe.toml").write_text(tomli_w.dumps(draft))
    before = project_inventory(project)
    chosen = ["local_exposure", "shadow_fade", "background"]
    value = json.loads(saved_recipe(project, selected["revision"], chosen, reference=True))
    assert value["sections"] == {
        "local_exposure": {"ev": 0.5},
        "shadow_fade": {"amount": 0.25, "preserve_highlights": 0},
        "background": {"color_srgb": "#14283C", "variation": 0},
    }
    assert set(value) == {"schema_version", "kind", "name", "sections", "reference"}
    raw = base64.b64decode(value["reference"]["png_base64"])
    with Image.open(io.BytesIO(raw)) as image:
        assert image.size == (6, 4) and image.info == {}
        assert image.getpixel((0, 0)) == (20, 40, 60)
        # Full alpha: exposure gain sqrt(2), then Shadow gain 2**(-6*0.25).
        # Independent scalar sRGB arithmetic includes each saved RGB16 quantization.
        assert image.getpixel((5, 0)) == (55, 84, 113)
        # Both effect areas protect this nonempty full/partial-alpha source sample.
        assert image.getpixel((2, 1)) != image.getpixel((5, 0))
    assert project_inventory(project) == before

    def forbidden_reference(*args, **kwargs):
        raise AssertionError("Unchecked reference must not render")

    monkeypatch.setattr(appearance_module(), "render_saved_result", forbidden_reference)
    assert json.loads(saved_recipe(project, selected["revision"], chosen))["reference"] is None
    assert project_inventory(project) == before


def test_recipe_spatial_defaults_select_saved_shape_without_geometry(tmp_path):
    from test_effects import fixture_project
    from test_spatial_fade import arc_settings, spatial_request, spatial_settings

    from blackmask import operations

    project, _, _ = fixture_project(tmp_path)
    settings = spatial_settings(6, 4)
    settings["oval"].update(transition_width=0.5, amount=0.3)
    settings["arcs"] = [
        arc_settings(
            center_xy=[3, 2],
            half_span=2,
            bend=-1,
            end_softness=0.5,
            transition_width=2,
            amount=0.8,
            enabled=False,
        )
    ]
    selected = operations.apply_operation(project, spatial_request(project, settings))
    for shape, fraction, amount in [("oval", 0.1, 0.3), (settings["arcs"][0]["id"], 0.4, 0.8)]:
        value = json.loads(
            saved_recipe(project, selected["revision"], ["spatial_fade"], shape=shape)
        )
        assert value["sections"] == {
            "spatial_fade": {
                "transition_subject_fraction": fraction,
                "amount": amount,
                "preserve_highlights": 0,
            }
        }
        assert shape not in json.dumps(value)
    for shape in (None, "missing", True):
        with pytest.raises(ValueError):
            saved_recipe(project, selected["revision"], ["spatial_fade"], shape=shape)


@pytest.mark.parametrize("changed", ["state.json", "source.json", "manifest", "operand"])
def test_recipe_creation_rejects_mid_render_source_or_operand_change(
    tmp_path, monkeypatch, changed
):
    from test_background import background_request
    from test_effects import fixture_project
    from test_ingest import saved_raster

    from blackmask import operations

    project, _, _ = fixture_project(tmp_path)
    selected = operations.apply_operation(project, background_request(project))
    recipes = appearance_module()
    original_render = recipes.render_saved_result

    def racing_render(*args):
        pixels = original_render(*args)
        relative = (
            f"revisions/{selected['revision']}/manifest.json"
            if changed == "manifest"
            else f"revisions/{selected['revision']}/foreground_rgb16.tif"
            if changed == "operand"
            else changed
        )
        path = saved_raster(project / relative)
        path.write_bytes(path.read_bytes() + b"\n")
        return pixels

    monkeypatch.setattr(recipes, "render_saved_result", racing_render)
    with pytest.raises(ValueError):
        saved_recipe(project, selected["revision"], ["background"], reference=True)


def test_recipe_creation_rejects_missing_sections_stale_hash_and_bad_selection(tmp_path):
    from test_effects import fixture_project

    project, _, selected = fixture_project(tmp_path)
    for sections, shape in [
        (["local_exposure"], None),
        (["background", "background"], None),
        (["background"], "oval"),
        ([], None),
    ]:
        with pytest.raises(ValueError):
            saved_recipe(project, selected["revision"], sections, shape=shape)
    with pytest.raises(ValueError):
        appearance_module().appearance_recipe_from_revision(
            project, selected["revision"], "0" * 64, "Wrong source", ["background"], None, False
        )
