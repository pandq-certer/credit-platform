import logging
import os
import uuid
from contextlib import asynccontextmanager

import yaml
from fastapi import FastAPI, File, Header, UploadFile
from fastapi.responses import JSONResponse

from .engine import OcrEngine, make_block, sha256_bytes
from .preprocess import decode_image, estimate_skew_angle, preprocess
from .quality import assess, detail

CONFIG_PATH = os.environ.get("OCR_CONFIG", "/app/config.yaml")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ocr")

MAGIC = {
    b"\xff\xd8\xff": "jpeg",
    b"\x89PNG\r\n\x1a\n": "png",
    b"BM": "bmp",
    b"II*\x00": "tiff",
    b"MM\x00*": "tiff",
    b"RIFF": "webp",
}
MAX_BYTES = 30 * 1024 * 1024

engine: OcrEngine


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    engine = OcrEngine(CONFIG.get("ocr", {}))
    yield


app = FastAPI(title="SYS-01 OCR Service", version="1.0.0", lifespan=lifespan)


def _err(code: int, msg: str, trace_id: str, reasons=None):
    body = {"error_code": code, "message": msg, "trace_id": trace_id}
    if reasons is not None:
        body["refuse_reasons"] = reasons
    return JSONResponse(status_code=400, content=body)


def _supported(data: bytes) -> bool:
    return any(data.startswith(m) for m in MAGIC)


async def _handle(file: UploadFile, trace_id: str):
    data = await file.read()
    if not data:
        return _err(40001, "empty file", trace_id)
    if len(data) > MAX_BYTES:
        return _err(40001, "file too large (>30MB)", trace_id)
    if not _supported(data):
        return _err(40001, "unsupported image format", trace_id)

    img = decode_image(data)
    if img is None:
        return _err(40002, "image decode failed", trace_id)

    skew = estimate_skew_angle(img)
    score, reasons = assess(img, skew)
    min_score = float(CONFIG.get("quality", {}).get("min_score", 0.6))
    if score < min_score:
        return _err(
            40003,
            f"quality below threshold ({score} < {min_score})",
            trace_id,
            reasons,
        )

    try:
        img = preprocess(img, CONFIG.get("preprocess", {}))
        raw = engine.infer(img)
    except Exception as e:  # noqa: BLE001
        log.exception("ocr failed trace=%s", trace_id)
        return _err(40002, f"ocr failed: {e}", trace_id)

    h, w = img.shape[:2]
    if not raw:
        return _err(40003, "no text detected", trace_id, reasons or ["BLUR"])
    sha = sha256_bytes(data)
    parser = f"paddleocr-3.7.0"
    blocks = [
        make_block(sha, 1, i, b["text"], b["score"], b["poly"], w, h, trace_id, parser)
        for i, b in enumerate(raw, start=1)
    ]
    return {
        "trace_id": trace_id,
        "file_sha256": sha,
        "page": 1,
        "width": w,
        "height": h,
        "model": engine.model_name,
        "blocks": blocks,
        "quality": {"score": score, "refuse_reasons": reasons},
    }


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "model": engine.model_name}


@app.post("/ocr")
async def ocr(file: UploadFile = File(...), x_trace_id: str | None = Header(default=None)):
    return await _handle(file, x_trace_id or uuid.uuid4().hex)


@app.post("/v1/ocr")
async def ocr_v1(file: UploadFile = File(...), x_trace_id: str | None = Header(default=None)):
    return await _handle(file, x_trace_id or uuid.uuid4().hex)


@app.post("/v1/quality")
async def quality_v1(file: UploadFile = File(...), x_trace_id: str | None = Header(default=None)):
    """图像质量明细（供 image-agent 质检链路使用）：只评估不识别。"""
    trace_id = x_trace_id or uuid.uuid4().hex
    data = await file.read()
    if not data:
        return _err(40001, "empty file", trace_id)
    if len(data) > MAX_BYTES:
        return _err(40001, "file too large (>30MB)", trace_id)
    if not _supported(data):
        return _err(40001, "unsupported image format", trace_id)

    img = decode_image(data)
    if img is None:
        return _err(40002, "image decode failed", trace_id)

    skew = estimate_skew_angle(img)
    score, reasons = assess(img, skew)
    min_score = float(CONFIG.get("quality", {}).get("min_score", 0.6))
    h, w = img.shape[:2]
    dims = detail(img, skew)
    return {
        "trace_id": trace_id,
        "file_sha256": sha256_bytes(data),
        "width": w,
        "height": h,
        "quality_score": score,
        "passed": score >= min_score,
        "refuse_reasons": reasons,
        **dims,
        # 未实现项显式声明，避免下游把缺省 0 当成"已检测且合格"
        "unsupported_metrics": ["occlusion"],
    }
