import math
import subprocess
import sys

import numpy as np
import pytest

from blackmask import mist
from blackmask.project import ProjectError


def settings(width=64, height=48, **changes):
    return {
        "enabled": True,
        "density": 0.72,
        "tint_srgb": "#8c9192",
        "wisp_size": 0.22,
        "stretch": 2,
        "rotation_degrees": 25,
        "seed": 1,
        "coverage": {
            "center_xy": [width / 2, height / 2],
            "radii_xy": [width, height],
            "softness": 0.72,
        },
        **changes,
    }


def vapor_settings(width=64, height=48, **changes):
    return {
        "style": "vapor",
        "enabled": True,
        "density": 1.0,
        "tint_srgb": "#3C403E",
        "focus_xy": [width * 0.53, height * 0.405],
        "rotation_degrees": 55,
        "seed": 1,
        **changes,
    }


def test_vapor_can_subdue_a_petal_and_lift_the_backdrop_around_clear_detail():
    width, height = 272, 361
    config = mist.validate_mist_settings(vapor_settings(width, height), width, height)
    density = mist.make_mist_density(config, (width, height))
    assert density.dtype == np.uint16
    assert not density[142:152, 139:149].any()
    bank = density[253:267, 205:219]
    assert bank.mean() > 0.55 * 65535
    assert bank.mean() > 2 * density[51:65, 141:155].mean()
    assert density[345:, 258:].max() < 0.06 * 65535
    assert np.ptp(bank) > 0
    y, x = np.mgrid[253:267, 205:219]
    np.testing.assert_array_equal(
        mist.sample_mist_density(config, (width, height), x + 0.5, y + 0.5), bank
    )
    midpoint = mist.make_mist_density(dict(config, density=0.5), (width, height))
    assert np.max(np.abs(midpoint.astype(float) * 2 - density)) <= 1
    assert not mist.make_mist_density(dict(config, density=0), (width, height)).any()

    backdrop, gold = np.array([[11, 12, 12], [203, 145, 12]], dtype=np.uint16) * 257
    incoming = np.array([[backdrop, gold, gold, gold]])
    density_row = np.array([[bank[0, 0], bank[0, 0], bank[0, 0], density[147, 144]]])
    clear = np.array([[0, 0, 65535, 0]], dtype=np.uint16)
    result = mist.blend_mist_into_result(incoming.copy(), density_row, clear, config)
    assert result[0, 0, 0] > backdrop[0]
    assert result[0, 1, 0] < gold[0]
    np.testing.assert_array_equal(result[0, 2:], incoming[0, 2:])


@pytest.mark.parametrize(
    ("footprint", "expected"),
    [
        (1, [0, 61061, 19452, 7822, 0, 60122, 14295]),
        (29.25, [0, 57871, 18554, 7851, 0, 57923, 13740]),
    ],
)
def test_vapor_v1_native_and_minified_samples_match_scalar_reference(footprint, expected):
    size = (272, 361)
    config = mist.validate_mist_settings(vapor_settings(*size), *size)
    # Independently evaluated v1 field at focus, bank, plume, faded edges and
    # two points outside the capture as sampled by framed export.
    x = np.array([144.5, 210.5, 144.5, 16.5, 259.5, 275.5, -1.5])
    y = np.array([146.5, 271.5, 54.5, 210.5, 345.5, 260.5, 92.5])
    np.testing.assert_array_equal(mist.sample_mist_density(config, size, x, y, footprint), expected)


def test_vapor_bank_rotates_about_an_off_center_focus():
    portrait = vapor_settings(80, 160, focus_xy=[6, 110], rotation_degrees=0)
    landscape = dict(portrait, focus_xy=[50, 6], rotation_degrees=90)
    x = np.array([10.5, 35.5, 45.5, 57.5])
    y = np.array([112.5, 119.5, 128.5, 131.5])
    expected = mist.sample_mist_density(portrait, (80, 160), x, y)
    assert expected[0] == 0 and np.count_nonzero(expected) >= 2
    np.testing.assert_array_equal(
        mist.sample_mist_density(landscape, (160, 80), 160 - y, x), expected
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"style": "unknown"},
        {"focus_xy": [65, 12]},
        {"focus_xy": [True, 12]},
        {"focus_xy": [0, float("nan")]},
        {"coverage": {}},
        {"seed": True},
    ],
)
def test_vapor_settings_are_closed_even_when_disabled(changes):
    with pytest.raises(ProjectError):
        mist.validate_mist_settings(vapor_settings(enabled=False, **changes), 64, 48)


def _scalar_density(config, size, x, y, footprint=1):
    def smooth(value):
        t = max(0, min(1, value))
        return t**2 * (3 - 2 * t)

    def fade(t):
        return 6 * t**5 - 15 * t**4 + 10 * t**3

    def lattice(x, y, octave):
        modulus = 2**32
        bits = (
            (x * 2654435761) ^ (y * 2246822519) ^ config["seed"] ^ ((octave + 1) * 3266489917)
        ) % modulus
        bits = ((bits ^ (bits // 65536)) * 2146121005) % modulus
        bits = ((bits ^ (bits // 32768)) * 2221713035) % modulus
        return (bits ^ (bits // 65536)) / (modulus - 1)

    coverage = config["coverage"]
    dx, dy = x - coverage["center_xy"][0], y - coverage["center_xy"][1]
    angle = math.radians(config["rotation_degrees"])
    u = dx * math.cos(angle) + dy * math.sin(angle)
    v = dy * math.cos(angle) - dx * math.sin(angle)
    radius = math.hypot(u / coverage["radii_xy"][0], v / coverage["radii_xy"][1])
    field = 0.0
    for octave, weight in enumerate((4, 2, 1)):
        wavelength = max(16, min(size) * config["wisp_size"]) / 2**octave
        tx, ty = u / config["stretch"] / wavelength, v / wavelength
        ix, iy = math.floor(tx), math.floor(ty)
        wx, wy = fade(tx - ix), fade(ty - iy)
        value = sum(
            lattice(ix + a, iy + b, octave) * (wx if a else 1 - wx) * (wy if b else 1 - wy)
            for a in (0, 1)
            for b in (0, 1)
        )
        gain = smooth((wavelength / footprint - 2) / 2)
        field += weight * (0.5 + gain * (value - 0.5)) / 7
    return round(
        65535
        * config["density"]
        * smooth((1 - radius) / coverage["softness"])
        * smooth((field - 0.30) / 0.55)
    )


def test_native_and_cropped_density_match_scalar_signed_coordinate_oracle():
    size = (64, 48)
    config = mist.validate_mist_settings(settings(*size), *size)
    points = [(-4.5, 18.5), (4.5, 3.5), (31.5, 23.5), (52.5, 39.5), (100.5, 24.5)]
    x, y = map(np.asarray, zip(*points, strict=True))
    for footprint in (1, 5.2):
        assert mist.sample_mist_density(config, size, x, y, footprint).tolist() == [
            _scalar_density(config, size, cx, cy, footprint) for cx, cy in points
        ]
    native = mist.make_mist_density(config, size)
    assert native.dtype == np.uint16
    assert native[y[1:4].astype(int), x[1:4].astype(int)].tolist() == [
        _scalar_density(config, size, cx, cy) for cx, cy in points[1:4]
    ]
    assert _scalar_density(config, size, *points[-1]) == 0


def test_density_stays_stable_across_processes_and_varies_with_pattern_controls():
    size = (128, 96)
    config = mist.validate_mist_settings(settings(*size), *size)
    x = np.array([-4.5, 19.5, 39.5, 70.5])
    y = np.array([37.5, 19.5, 55.5, 70.5])
    expected = [_scalar_density(config, size, cx, cy) for cx, cy in zip(x, y, strict=True)]
    assert expected == [15012, 31290, 47073, 39594]
    assert (
        mist.make_mist_density(config, size)[y[1:].astype(int), x[1:].astype(int)].tolist()
        == expected[1:]
    )
    script = (
        "import numpy as np\nfrom blackmask.mist import sample_mist_density\n"
        f"print(sample_mist_density({config!r}, {size!r}, np.array({x.tolist()!r}), "
        f"np.array({y.tolist()!r})).tolist())"
    )
    assert subprocess.check_output([sys.executable, "-c", script], text=True).strip() == str(
        expected
    )
    for change in (
        {"seed": 2**32 - 1},
        {"wisp_size": 0.47},
        {"stretch": 3.4},
        {"rotation_degrees": 110},
    ):
        varied = mist.validate_mist_settings(dict(config, **change), *size)
        assert mist.sample_mist_density(varied, size, x, y).tolist() != expected


@pytest.mark.parametrize(
    "change",
    [
        {"density": True},
        {"density": float("nan")},
        {"enabled": 1},
        {"seed": -1},
        {"seed": 2**32},
        {"seed": 1.0},
        {"stretch": 0.99},
        {"rotation_degrees": 360},
        {"wisp_size": 0.61},
        {"tint_srgb": "#123"},
        {"extra": 0},
        {"coverage": {"center_xy": [65, 10], "radii_xy": [30, 30], "softness": 1}},
        {"coverage": {"center_xy": [2, 10], "radii_xy": [0, 30], "softness": 1}},
        {"coverage": {"center_xy": [2, 10], "radii_xy": [30, 30], "softness": 0.04}},
    ],
)
def test_closed_settings_reject_invalid_values(change):
    with pytest.raises(ProjectError):
        mist.validate_mist_settings(settings(**change), 64, 48)


def test_linear_blend_bypasses_off_zero_and_clear_and_tints_both_sides():
    config = mist.validate_mist_settings(settings(4, 1, tint_srgb="#ffffff"), 4, 1)
    assert config["tint_srgb"] == "#FFFFFF"
    incoming = np.array(
        [[[0, 0, 0], [20000, 5000, 1000], [40000, 20000, 7000], [1, 2, 3]]], np.uint16
    )
    density = np.array([[32768, 32768, 40000, 0]], np.uint16)
    clear = np.array([[0, 32768, 65535, 0]], np.uint16)
    assert np.array_equal(
        mist.blend_mist_into_result(incoming.copy(), density, clear, dict(config, enabled=False)),
        incoming,
    )
    assert np.array_equal(
        mist.blend_mist_into_result(incoming.copy(), density, clear, dict(config, density=0)),
        incoming,
    )
    result = incoming.copy()
    assert mist.blend_mist_into_result(result, density, clear, config) is result
    assert result[0, 0].tolist() == [48192] * 3
    expected = []
    for channel in incoming[0, 1]:
        encoded = int(channel) / 65535
        linear = ((encoded + 0.055) / 1.055) ** 2.4 if encoded > 0.04045 else encoded / 12.92
        opacity = 32768 * (65535 - 32768) / 65535**2
        out = linear + opacity * (1 - linear)
        expected.append(round(65535 * (1.055 * out ** (1 / 2.4) - 0.055)))
    assert result[0, 1].tolist() == expected
    np.testing.assert_array_equal(result[:, 2:], incoming[:, 2:])


def test_clear_area_feathers_inward_and_unconditionally_protects_saved_values():
    area = {
        "regions": [
            {
                "id": "clear",
                "role": "support",
                "shape": "rectangle",
                "xyxy": [1, 1, 8, 8],
                "feather_px": 3,
            }
        ],
        "protection": [],
    }
    hard = np.zeros((10, 12), dtype=np.bool_)
    hard[0, 10] = True
    clear = mist.make_mist_clear(area, "synthetic", hard)
    assert clear.dtype == np.uint16
    assert [clear[3, x] for x in (0, 1, 2, 3, 7, 8)] == [0, 21845, 43690, 65535, 21845, 0]
    assert clear[0, 10] == 65535


def test_clear_area_bounds_are_checked_before_rasterization():
    stroke = {
        "id": "clear",
        "role": "support",
        "shape": "stroke",
        "points": [[1, 1]],
        "radius_px": 1,
        "feather_px": 1,
    }
    with pytest.raises(ProjectError, match="64 shapes"):
        mist.validate_mist_area({"regions": [stroke] * 65, "protection": []}, "synthetic", 12, 10)
    with pytest.raises(ProjectError, match="8192 stroke points"):
        mist.validate_mist_area(
            {"regions": [dict(stroke, points=[[1, 1]] * 8193)], "protection": []},
            "synthetic",
            12,
            10,
        )
