import numpy as np
import pytest

from blackmask import guidance


def region(role, shape="rectangle", **values):
    return {"id": role, "role": role, "shape": shape, "xyxy": [1, 1, 5, 4], **values}


def document(regions):
    return {
        "schema_version": 2,
        "developed_id": "a" * 64,
        "width": 7,
        "height": 5,
        "regions": regions,
    }


def raster(regions, **kwargs):
    return guidance.rasterize_regions(document(regions), **kwargs)


def test_native_half_open_labels_and_unknown_corridor():
    result = raster([region("foreground"), region("unknown", xyxy=[2, 0, 3, 5])])
    assert set(np.unique(result.trimap)) == {128, 255}
    assert result.trimap[1, 1] == 255 and result.trimap[3, 4] == 255
    assert result.trimap[4, 1] == 128 and result.trimap[1, 5] == 128
    assert np.all(result.trimap[:, 2] == 128)


def test_negative_hints_and_kept_membership_do_not_certify_background():
    r = raster(
        [{"id": "hint", "role": "remove", "shape": "point", "xy": [1, 2], "group_id": "wing"}]
    )
    assert np.all(r.trimap == 128)


def test_foreground_background_conflict_rejected_before_unknown_precedence():
    with pytest.raises(ValueError, match="foreground.*background"):
        raster([region("foreground"), region("background"), region("unknown")])


def test_support_inward_feather_zero_and_scope_clip():
    zero = raster([region("support", feather_px=0)], scope_xyxy=[0, 0, 3, 5]).support16
    assert np.count_nonzero(zero) == 6 and np.all(zero[1:4, 1:3] == 65535)
    feather = raster([region("support", feather_px=2)]).support16
    assert feather[1, 1] == 32768 and feather[2, 2] == 65535
    assert feather[0, 2] == 0


def test_stroke_radius_native_and_categorical():
    r = raster(
        [
            {
                "id": "line",
                "role": "background",
                "shape": "stroke",
                "points": [[1, 2], [5, 2]],
                "radius_px": 1,
            }
        ]
    )
    assert r.trimap[2, 0] == 0 and r.trimap[1, 3] == 0
    assert r.trimap[0, 3] == 128 and r.trimap[2, 6] == 0
    assert set(np.unique(r.trimap)) == {0, 128}


@pytest.mark.parametrize(
    "change",
    [
        {"xyxy": [1, 1, 8, 3]},
        {"xyxy": [1, 1, 1, 3]},
        {"xyxy": [True, 1, 3, 4]},
        {"unexpected": 1},
        {"role": "prose"},
    ],
)
def test_invalid_geometry_unknown_keys_and_roles(change):
    with pytest.raises(ValueError):
        raster([{**region("foreground"), **change}])


def test_saved_partial_locks_conflict_and_new_project_rejection():
    lock = region("lock", revision="rev-001")
    with pytest.raises(ValueError, match="saved"):
        raster([lock])
    saved = np.full((5, 7), 12345, dtype=np.uint16)
    r = raster([lock], saved_alpha={"rev-001": saved})
    assert np.count_nonzero(r.protection) == 12
    assert np.all(r.lock_values16[r.protection] == 12345)
    with pytest.raises(ValueError, match="lock"):
        raster([lock, region("foreground")], saved_alpha={"rev-001": saved})


def test_change_needed_cores_cannot_expand_feathered_support():
    saved = np.full((5, 7), 12345, dtype=np.uint16)
    with pytest.raises(ValueError, match="support"):
        raster([region("foreground"), region("support", feather_px=2)], parent_alpha=saved)


def proposal(mask, policy="opaque_core", erosion=1, dilation=1, regions=None, **kwargs):
    guides = document(regions or [])
    group = {
        "id": "object",
        "keep": True,
        "material_policy": policy,
        "selected_candidate": 1,
        "morphology": {"foreground_erosion_px": erosion, "unknown_dilation_px": dilation},
    }
    candidates = [{"group_id": "object", "selected": True, "mask": mask}]
    return guidance.build_trimap_proposal(guides, [group], candidates, **kwargs)


def test_morphology_native_core_and_boundary_independent_geometry():
    mask = np.zeros((5, 7), dtype=bool)
    mask[1:4, 1:6] = True
    result, boundary = proposal(mask)
    expected = np.full((5, 7), 128, dtype=np.uint8)
    expected[2, 2:5] = 255
    np.testing.assert_array_equal(result.trimap, expected)
    expected_boundary = np.array(
        [
            [0, 1, 1, 1, 1, 1, 0],
            [1, 1, 1, 1, 1, 1, 1],
            [1, 1, 0, 0, 0, 1, 1],
            [1, 1, 1, 1, 1, 1, 1],
            [0, 1, 1, 1, 1, 1, 0],
        ],
        dtype=bool,
    )
    np.testing.assert_array_equal(boundary, expected_boundary)
    changed, _ = proposal(mask, erosion=0, dilation=0)
    assert np.count_nonzero(changed.trimap == 255) == 15
    assert not np.any(proposal(np.zeros_like(mask))[0].trimap == 255)


def test_morphology_image_exterior_and_holes_never_filled():
    mask = np.ones((5, 7), dtype=bool)
    mask[2, 3] = False
    result, _ = proposal(mask)
    assert np.all(result.trimap[0] == 128) and np.all(result.trimap[:, 0] == 128)
    assert result.trimap[2, 3] == 128 and result.trimap[2, 2] == 128
    assert result.trimap[1, 1] == 255


def test_fragile_proposal_stays_unknown_except_explicit_solid_core():
    mask = np.ones((5, 7), dtype=bool)
    result, _ = proposal(
        mask, policy="unknown_interior", regions=[region("foreground", xyxy=[2, 2, 3, 3])]
    )
    assert np.count_nonzero(result.trimap == 255) == 1 and result.trimap[2, 2] == 255
    assert np.count_nonzero(result.trimap == 0) == 0
    corridor, _ = proposal(mask, regions=[region("unknown", xyxy=[2, 0, 3, 5])])
    assert np.all(corridor.trimap[:, 2] == 128)


def test_proposal_conflicts_partial_locks_and_support_do_not_bypass_guards():
    mask = np.ones((5, 7), dtype=bool)
    with pytest.raises(ValueError, match="foreground.*background"):
        proposal(mask, regions=[region("background", xyxy=[2, 2, 3, 3])])
    saved = np.full((5, 7), 12345, dtype=np.uint16)
    with pytest.raises(ValueError, match="lock"):
        proposal(mask, regions=[region("lock", revision="rev-001")], saved_alpha={"rev-001": saved})
    with pytest.raises(ValueError, match="support"):
        proposal(
            mask,
            regions=[region("support", feather_px=2)],
            parent_alpha=saved,
            scope_xyxy=[0, 0, 3, 5],
        )
    # A verified BG point outside the proposed core is retained; no complement becomes BG.
    result, _ = proposal(
        mask, regions=[{"id": "bg", "role": "background", "shape": "point", "xy": [0, 0]}]
    )
    assert result.trimap[0, 0] == 0 and np.count_nonzero(result.trimap == 0) == 1


def test_unclassified_fragile_selection_overrides_other_group_proposed_core():
    guides = document([])
    body = np.ones((5, 7), dtype=bool)
    wing = np.zeros_like(body)
    wing[:, 3] = True
    groups = [
        {
            "id": "body",
            "keep": True,
            "material_policy": "opaque_core",
            "selected_candidate": 0,
            "morphology": {"foreground_erosion_px": 1, "unknown_dilation_px": 1},
        },
        {
            "id": "wing",
            "keep": True,
            "material_policy": "unknown_interior",
            "selected_candidate": 0,
        },
    ]
    candidates = [
        {"group_id": "body", "selected": True, "mask": body},
        {"group_id": "wing", "selected": True, "mask": wing},
    ]
    result, boundary = guidance.build_trimap_proposal(guides, groups, candidates)
    assert np.all(result.trimap[:, 3] == 128) and result.trimap[2, 2] == 255
    assert np.all(boundary[:, 3])


def test_native_morphology_margins_bounded_by_master():
    with pytest.raises(ValueError, match="margins"):
        proposal(np.ones((5, 7), dtype=bool), erosion=8)
