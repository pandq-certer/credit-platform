import cv2
import numpy as np


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def _glare_ratio(gray) -> float:
    """排除页面白底后的过曝占比（高光/反光）。"""
    white = (gray >= 250).astype(np.uint8)
    total = white.size
    if not white.any():
        return 0.0
    n, _labels, stats, _ = cv2.connectedComponentsWithStats(white, connectivity=8)
    if n <= 1:
        return float(white.sum()) / total
    bg_area = int(stats[1:, cv2.CC_STAT_AREA].max())
    return float(white.sum() - bg_area) / total


def detail(img, skew_angle: float) -> dict:
    """五维质量明细：清晰度/亮度/反光/倾斜/有效分辨率，另附 RMS 对比度。

    仅供 /v1/quality 暴露明细使用，不参与 assess() 的加权综合分（保持既有阈值口径不变）。
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]

    lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    mean = float(gray.mean())
    glare_ratio = _glare_ratio(gray)
    min_side = min(h, w)

    blur_s = _clamp(lap_var / 200.0)
    if mean < 120:
        bright_s = _clamp((mean - 30.0) / 90.0)
    else:
        bright_s = 1.0 - _clamp((mean - 245.0) / 10.0)
    glare_s = 1.0 - _clamp((glare_ratio - 0.15) / 0.35)
    skew_s = 1.0 - _clamp(abs(skew_angle) / 10.0)
    dpi_s = 1.0 if min_side >= 1000 else _clamp(min_side / 1000.0)
    # RMS 对比度：灰度标准差 / 64 视为满值
    contrast_s = _clamp(float(gray.std()) / 64.0)

    return {
        "clarity": round(blur_s, 4),
        "brightness": round(bright_s, 4),
        "contrast": round(contrast_s, 4),
        "blur": round(1.0 - blur_s, 4),
        "glare": round(glare_ratio, 4),
        "skew": round(abs(skew_angle), 4),
        "dpi": round(dpi_s, 4),
    }


def assess(img, skew_angle: float):
    """五维质量评估：清晰度/亮度/反光/倾斜/有效分辨率。"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]

    lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    mean = float(gray.mean())
    glare_ratio = _glare_ratio(gray)
    min_side = min(h, w)

    blur_s = _clamp(lap_var / 200.0)
    if mean < 120:
        bright_s = _clamp((mean - 30.0) / 90.0)
    else:
        bright_s = 1.0 - _clamp((mean - 245.0) / 10.0)
    glare_s = 1.0 - _clamp((glare_ratio - 0.15) / 0.35)
    skew_s = 1.0 - _clamp(abs(skew_angle) / 10.0)
    dpi_s = 1.0 if min_side >= 1000 else _clamp(min_side / 1000.0)

    reasons = []
    if blur_s < 0.3:
        reasons.append("BLUR")
    if bright_s < 0.3:
        reasons.append("TOO_DARK")
    if glare_s < 0.3:
        reasons.append("GLARE")
    if skew_s < 0.3:
        reasons.append("SKEW")
    if dpi_s < 0.3:
        reasons.append("LOW_DPI")

    score = float(
        np.average(
            [blur_s, bright_s, glare_s, skew_s, dpi_s],
            weights=[0.30, 0.25, 0.15, 0.15, 0.15],
        )
    )
    return round(score, 4), reasons
