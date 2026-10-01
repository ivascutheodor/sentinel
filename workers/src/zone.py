import json
from pathlib import Path

import cv2
import numpy as np


def load_zone(path: Path) -> np.ndarray:
    with open(path) as f:
        points = json.load(f)
    return np.array(points, np.int32).reshape((-1, 1, 2))


def foot_point(box: tuple[int, int, int, int]) -> tuple[int, int]:
    """Bottom-center of a bounding box: where the person touches the ground."""
    x1, _, x2, y2 = box
    return (x1 + x2) // 2, y2


def is_in_zone(zone: np.ndarray, point: tuple[int, int]) -> bool:
    # pointPolygonTest: > 0 inside, 0 on the edge, < 0 outside
    point = (float(point[0]), float(point[1]))
    return cv2.pointPolygonTest(zone, point, False) >= 0
