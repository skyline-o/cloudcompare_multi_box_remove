from dataclasses import dataclass
from typing import List

import numpy as np


@dataclass(frozen=True)
class BoxSpec:
    name: str
    source_key: str
    lo: np.ndarray
    hi: np.ndarray

    @classmethod
    def from_corners(cls, name, source_key, corner_a, corner_b):
        a = np.asarray(corner_a, dtype=np.float64).reshape(3)
        b = np.asarray(corner_b, dtype=np.float64).reshape(3)
        return cls(
            name=str(name),
            source_key=str(source_key),
            lo=np.minimum(a, b),
            hi=np.maximum(a, b),
        )

    @property
    def dimensions(self):
        return self.hi - self.lo


def add_unique_box(boxes: List[BoxSpec], box: BoxSpec) -> bool:
    if any(existing.source_key == box.source_key for existing in boxes):
        return False
    boxes.append(box)
    return True


def compute_keep_mask(points, boxes):
    pts = np.asarray(points)
    if pts.ndim != 2 or pts.shape[1] != 3:
        raise ValueError('points must have shape (N, 3)')

    keep = np.ones(pts.shape[0], dtype=bool)
    for box in boxes:
        inside = (
            (pts[:, 0] >= box.lo[0]) & (pts[:, 0] <= box.hi[0]) &
            (pts[:, 1] >= box.lo[1]) & (pts[:, 1] <= box.hi[1]) &
            (pts[:, 2] >= box.lo[2]) & (pts[:, 2] <= box.hi[2])
        )
        keep &= ~inside
    return keep
