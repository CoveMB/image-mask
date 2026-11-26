from copy import deepcopy

import pytest
from test_background_pattern import pattern_settings

from blackmask import background_pattern_generation as generator
from blackmask.background_pattern import normalize_background_pattern
from blackmask.project import ProjectError, _json_bytes, digest


def test_pattern_generation_reference_seeds_and_style_members():
    assert generator.default_pattern_seed("1" * 64, "mixed") == 450512810
    assert generator.default_pattern_seed("2" * 64, "mixed") == 3022267830
    assert digest(_json_bytes(generator.generate_background_pattern("mixed", 17, 9, 61))) == (
        "9b34e0b36ebee696ee8f01c67521376ef3e6f8411d954b850df1bd97e72d74fe"
    )
    for style, ids in (
        ("waves", ["lower-wave", "side-wave"]),
        ("ovals", ["upper-oval", "side-oval"]),
        ("mixed", ["lower-wave", "side-wave", "upper-oval"]),
    ):
        for width, height in ((1, 1), (9, 61), (3072, 4080)):
            layout = generator.generate_background_pattern(style, 17, width, height)
            assert [shape["id"] for shape in layout] == ids
            assert (
                normalize_background_pattern(pattern_settings(shapes=layout), width, height)[
                    "shapes"
                ]
                == layout
            )


def test_pattern_generation_uses_distinct_editable_geometry():
    first = generator.generate_background_pattern("mixed", 17, 3072, 4080)
    frozen = deepcopy(first)
    first[0]["center_xy"][0] = 0
    assert generator.generate_background_pattern("mixed", 17, 3072, 4080) == frozen
    assert generator.generate_background_pattern("mixed", 18, 3072, 4080) != frozen
    assert generator.generate_background_pattern("mixed", 450512810, 3072, 4080) != (
        generator.generate_background_pattern("mixed", 3022267830, 3072, 4080)
    )


@pytest.mark.parametrize(
    "style, seed",
    [("missing", 17), ("mixed", True), ("mixed", -1), ("mixed", 2**32), ("waves", 1.5)],
)
def test_generator_rejects_invalid_requests(style, seed):
    with pytest.raises(ProjectError):
        generator.generate_background_pattern(style, seed, 9, 61)
