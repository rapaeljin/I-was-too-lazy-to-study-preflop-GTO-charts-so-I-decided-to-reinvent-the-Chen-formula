###############################################################################
# image processing
###############################################################################

import math
from typing import Optional, Tuple

import cv2
import numpy as np


GRID_N = 13
QUANT_STEP = 8

# Ignore grid line border
CELL_BORDER_FRAC = 0.08

# Use only bottom part of each cell to avoid white labels
CELL_SAMPLE_BOTTOM_FRAC = 1.0 / 3.0  # bottom 1/3


# -------------------------------------------------
# Internal utilities
# -------------------------------------------------

def _quantize_rgb(rgb: np.ndarray, step: int) -> np.ndarray:
    return (rgb // step) * step


def _tile_mode_color(tile_rgb: np.ndarray) -> Tuple[int, int, int]:
    q = _quantize_rgb(tile_rgb, QUANT_STEP).reshape(-1, 3)
    q_view = q.view([("r", np.uint8), ("g", np.uint8), ("b", np.uint8)]).reshape(-1)
    vals, counts = np.unique(q_view, return_counts=True)
    dominant = vals[np.argmax(counts)]
    return int(dominant["r"]), int(dominant["g"]), int(dominant["b"])


def _classify_color(rgb: Tuple[int, int, int], raise_class: bool) -> int:
    """
    Map RGB to fixed class ID:

    0 = blue
    1 = green
    2 = red
    3 = dark red (maroon)

    """
    r, g, b = rgb

    # 밝기
    brightness = (r + g + b) / 3

    # HSV로 hue 기반 분류가 더 안정적
    hsv = cv2.cvtColor(np.uint8([[rgb]]), cv2.COLOR_RGB2HSV)[0, 0]
    h, s, v = hsv

    # 파랑 (대략 90~140도 영역), 검정: FOLD
    if brightness < 20 or 90 <= h <= 140:
        return 0

    # 초록 (40~85도): CALL
    if 40 <= h < 90:
        return 1

    # 빨강 영역 (0~15 또는 165~180): RAISE or ALL-IN
    if h <= 15 or h >= 165:
        # 어두운 빨강: ALL-IN
        if raise_class and brightness < 100:
            return 3
        else:
            return 2

    # fallback: RGB dominance 기반
    if r > g and r > b:
        return 2 if brightness >= 90 else 3
    if g > r and g > b:
        return 1
    return 0


def _extract_grid(img_bgr: np.ndarray,
                  bbox: Tuple[int, int, int, int],
                  raise_class: bool):
    """
    Returns:
        ids  : (13,13) int32
        rgb  : (13,13,3) uint8
    """
    x1, y1, x2, y2 = bbox
    crop = img_bgr[y1:y2, x1:x2]
    if crop.size == 0:
        raise ValueError("Empty crop; bbox may be wrong.")

    crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)

    H, W = crop_rgb.shape[:2]
    ys = np.linspace(0, H, GRID_N + 1).astype(int)
    xs = np.linspace(0, W, GRID_N + 1).astype(int)

    ids = np.zeros((GRID_N, GRID_N), dtype=np.int32)
    colors = np.zeros((GRID_N, GRID_N, 3), dtype=np.uint8)

    palette = {}
    next_id = 0

    for r in range(GRID_N):
        for c in range(GRID_N):
            y_a, y_b = ys[r], ys[r + 1]
            x_a, x_b = xs[c], xs[c + 1]

            cell_h = y_b - y_a
            cell_w = x_b - x_a
            if cell_h <= 2 or cell_w <= 2:
                continue

            # 1) trim borders to avoid grid lines
            by = int(cell_h * CELL_BORDER_FRAC)
            bx = int(cell_w * CELL_BORDER_FRAC)

            inner_y1 = y_a + by
            inner_y2 = y_b - by
            inner_x1 = x_a + bx
            inner_x2 = x_b - bx

            if inner_y2 <= inner_y1 + 1 or inner_x2 <= inner_x1 + 1:
                # fallback to full cell if too tight
                inner_y1, inner_y2 = y_a, y_b
                inner_x1, inner_x2 = x_a, x_b

            # 2) use ONLY bottom 1/3 of the (inner) cell to avoid white text
            inner_h = inner_y2 - inner_y1
            sample_h = max(1, int(inner_h * CELL_SAMPLE_BOTTOM_FRAC))
            sample_y1 = inner_y2 - sample_h
            sample_y2 = inner_y2

            tile = crop_rgb[sample_y1:sample_y2, inner_x1:inner_x2]
            dom = _tile_mode_color(tile)
            colors[r, c] = dom

            ids[r, c] = _classify_color(dom, raise_class)

    return ids, colors


# -------------------------------------------------
# Public API
# -------------------------------------------------

def extract_grid13(
    image_path: str,
    bbox: Optional[Tuple[int, int, int, int]] = None,
    return_rgb: bool = False,
    raise_class=False
):
    """
    Parameters
    ----------
    image_path : str
        Path to image.
    bbox : (x1,y1,x2,y2), optional
        If provided, skip auto-detection.
    return_rgb : bool
        If True, returns (ids, rgb). Otherwise returns ids only.

    Returns
    -------
    (13,13) int32 ndarray (color IDs per cell)
    Optionally (ids, rgb) where rgb is (13,13,3) uint8 dominant RGB per cell.
    """
    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Failed to read image: {image_path}")

    ids, colors = _extract_grid(img, bbox, raise_class)
    return (ids, colors) if return_rgb else ids