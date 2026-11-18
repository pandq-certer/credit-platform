import cv2
import numpy as np


def decode_image(data: bytes):
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


def estimate_skew_angle(img) -> float:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coords = cv2.findNonZero(th)
    if coords is None or len(coords) < 50:
        return 0.0
    (_, _), (_, _), angle = cv2.minAreaRect(coords)
    if angle > 45:
        angle -= 90
    if angle < -45:
        angle += 90
    return float(angle)


def deskew(img):
    angle = estimate_skew_angle(img)
    if abs(angle) < 0.3 or abs(angle) > 20:
        return img
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(
        img, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def limit_max_side(img, max_side: int):
    h, w = img.shape[:2]
    longest = max(h, w)
    if longest <= max_side:
        return img
    scale = max_side / longest
    return cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)


def preprocess(img, cfg):
    if cfg.get("deskew", True):
        img = deskew(img)
    img = limit_max_side(img, int(cfg.get("max_side", 3000)))
    if cfg.get("denoise", False):
        img = cv2.fastNlMeansDenoisingColored(img, None, 5, 5, 7, 21)
    return img
