import numpy as np
import pytest

from bbox_core import BoxSpec, compute_keep_mask, add_unique_box


def test_boxspec_normalizes_min_max_and_dimensions():
    box = BoxSpec.from_corners('box1', 'id-1', [5, 1, 9], [2, 4, 3])
    np.testing.assert_allclose(box.lo, [2, 1, 3])
    np.testing.assert_allclose(box.hi, [5, 4, 9])
    np.testing.assert_allclose(box.dimensions, [3, 3, 6])


def test_compute_keep_mask_removes_union_and_boundary_points():
    points = np.array([
        [0, 0, 0],    # box1 boundary -> remove
        [1, 1, 1],    # box1 -> remove
        [2, 2, 2],    # keep
        [10, 10, 10], # box2 -> remove
        [11, 11, 11], # box2 boundary -> remove
        [20, 20, 20], # keep
    ], dtype=float)
    boxes = [
        BoxSpec.from_corners('b1', '1', [0, 0, 0], [1, 1, 1]),
        BoxSpec.from_corners('b2', '2', [9, 9, 9], [11, 11, 11]),
    ]
    mask = compute_keep_mask(points, boxes)
    assert mask.tolist() == [False, False, True, False, False, True]


def test_add_unique_box_rejects_same_source_key():
    boxes = []
    box = BoxSpec.from_corners('b1', 'same-id', [0, 0, 0], [1, 1, 1])
    assert add_unique_box(boxes, box) is True
    assert add_unique_box(boxes, box) is False
    assert len(boxes) == 1


def test_compute_keep_mask_rejects_bad_point_shape():
    with pytest.raises(ValueError):
        compute_keep_mask(np.array([1.0, 2.0, 3.0]), [])
