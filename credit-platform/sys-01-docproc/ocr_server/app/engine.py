import hashlib
import logging
import threading

import cv2
import numpy as np

log = logging.getLogger(__name__)


class OcrEngine:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.model_name = cfg.get("model", "PP-OCRv5_server")
        self._lock = threading.Lock()
        self._infer_lock = threading.Lock()
        self._ocr = None

    def _build(self):
        from paddleocr import PaddleOCR

        log.info("loading PaddleOCR model=%s", self.model_name)
        return PaddleOCR(
            lang=self.cfg.get("lang", "ch"),
            ocr_version=self.cfg.get("ocr_version", "PP-OCRv5"),
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=True,
            text_det_limit_side_len=int(self.cfg.get("det_limit_side_len", 2000)),
            text_det_box_thresh=float(self.cfg.get("det_db_box_thresh", 0.5)),
            text_rec_score_thresh=float(self.cfg.get("drop_score", 0.5)),
            return_word_box=bool(self.cfg.get("return_word_box", True)),
        )

    @property
    def ocr(self):
        if self._ocr is None:
            with self._lock:
                if self._ocr is None:
                    self._ocr = self._build()
        return self._ocr

    def infer(self, img):
        """返回 [{'text','score','poly'}...]，poly 为像素坐标 4 点。"""
        result = None
        with self._infer_lock:
            result = self.ocr.predict(img)
        if not result:
            return []
        res = result[0]
        texts = res["rec_texts"]
        scores = res["rec_scores"]
        polys = res["rec_polys"] if "rec_polys" in res else res.get("dt_polys")
        blocks = []
        for text, score, poly in zip(texts, scores, polys):
            pts = np.asarray(poly, dtype=float).reshape(-1, 2)
            blocks.append({"text": str(text), "score": float(score), "poly": pts})
        return blocks


def make_block(sha256: str, page: int, seq: int, text: str, score: float,
               poly, width: int, height: int, trace_id: str, parser: str) -> dict:
    pts = np.asarray(poly, dtype=float).reshape(-1, 2)
    xs = pts[:, 0] / max(width, 1)
    ys = pts[:, 1] / max(height, 1)
    xs = np.clip(xs, 0.0, 1.0)
    ys = np.clip(ys, 0.0, 1.0)
    polygon = [[round(float(x), 6), round(float(y), 6)] for x, y in zip(xs, ys)]
    bbox = [
        round(float(xs.min()), 6),
        round(float(ys.min()), 6),
        round(float(xs.max()), 6),
        round(float(ys.max()), 6),
    ]
    return {
        "block_id": f"{sha256}-p{page}-{seq:04d}",
        "page": page,
        "text": text,
        "bbox": bbox,
        "polygon": polygon,
        "confidence": round(float(score), 6),
        "parser": parser,
        "trace_id": trace_id,
    }


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
