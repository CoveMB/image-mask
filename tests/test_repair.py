"""Saved quantized repair arithmetic, independent hand-derived sentinels."""

import numpy as np
import pytest

from blackmask.repair import merge_alpha


@pytest.mark.parametrize(
    "policy,candidate,expected",
    [
        ("replace", 3000, 1667),
        ("increase-only", 500, 1000),
        ("decrease-only", 3000, 1000),
        ("increase-only", 3000, 1667),
        ("decrease-only", 500, 833),
    ],
)
def test_quantized_policy_sentinels(policy, candidate, expected):
    parent = np.full((2, 3), 1000, dtype=np.uint16)
    local = np.full((2, 3), candidate, dtype=np.uint16)
    support = np.array([[21845, 0, 65535], [65535, 21845, 0]], dtype=np.uint16)
    protected = np.array([[False, False, False], [True, False, False]])
    locked = np.full((2, 3), 12345, dtype=np.uint16)
    result = merge_alpha(parent, local, support, protected, locked, policy)
    assert result[0, 0] == expected
    assert result[0, 1] == result[1, 2] == 1000
    assert result[1, 0] == 12345
    assert result[0, 2] == (
        candidate
        if policy == "replace"
        else max(1000, candidate)
        if policy == "increase-only"
        else min(1000, candidate)
    )
