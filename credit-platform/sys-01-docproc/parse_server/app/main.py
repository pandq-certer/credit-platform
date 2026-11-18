import hashlib
import io
import logging
import os
import tempfile
import uuid

from fastapi import FastAPI, File, Form, Header, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pypdf import PdfReader

from . import db
from .ocr_plugin import OcrServiceError
from .pipeline import FORMAT_MAP, parse_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("parse")

OCR_BASE_URL = os.environ.get("SYS01_OCR_URL", "http://127.0.0.1:8101")
TMP_DIR = os.environ.get("SYS01_TMP_DIR", "/data/tmp")
MAX_BYTES = 100 * 1024 * 1024

app = FastAPI(title="SYS-01 Document Parse Service", version="1.0.0")


@app.on_event("startup")
def startup():
    os.makedirs(TMP_DIR, exist_ok=True)
    try:
        db.init_schema()
    except Exception as e:  # noqa: BLE001
        log.error("db init failed: %s", e)


@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "doc-parse", "ocr": OCR_BASE_URL}


class ReviewUpdate(BaseModel):
    status: str


@app.get("/v1/quality/review")
def list_quality_review(status: str = "pending", limit: int = 100):
    return {"items": db.list_reviews(status=status, limit=limit)}


@app.post("/v1/quality/review/{review_id}")
def update_quality_review(review_id: int, body: ReviewUpdate):
    if body.status not in ("pending", "confirmed", "rejected"):
        return _err(40001, "invalid status", "review")
    return {"updated": db.update_review(review_id, body.status)}


def _err(code: int, msg: str, trace_id: str, reasons=None, needs_manual=False):
    body = {"error_code": code, "message": msg, "trace_id": trace_id}
    if reasons:
        body["refuse_reasons"] = reasons
    if needs_manual:
        body["needs_manual"] = True
    return JSONResponse(status_code=400, content=body)


async def _handle(file: UploadFile, trace_id: str):
    name = file.filename or "upload"
    ext = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
    if ext not in FORMAT_MAP:
        return _err(40001, f"unsupported format: {ext}", trace_id)

    data = await file.read()
    if not data:
        return _err(40001, "empty file", trace_id)
    if len(data) > MAX_BYTES:
        return _err(40001, "file too large (>100MB)", trace_id)

    sha = hashlib.sha256(data).hexdigest()

    if ext == ".pdf":
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                db.save_failure(trace_id, sha, name, 40004)
                return _err(40004, "encrypted PDF", trace_id, needs_manual=True)
        except Exception:  # noqa: BLE001
            pass

    fd, path = tempfile.mkstemp(suffix=ext, dir=TMP_DIR)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        result = parse_file(path, name, trace_id, OCR_BASE_URL)
        result["file_sha256"] = sha
        try:
            db.save_result(result)
        except Exception as e:  # noqa: BLE001
            log.error("db save failed trace=%s: %s", trace_id, e)
        return result
    except OcrServiceError as e:
        db.save_failure(trace_id, sha, name, e.code)
        return _err(e.code, str(e), trace_id, e.reasons)
    except ValueError as e:
        db.save_failure(trace_id, sha, name, 40001)
        return _err(40001, str(e), trace_id)
    except Exception as e:  # noqa: BLE001
        log.exception("parse failed trace=%s", trace_id)
        db.save_failure(trace_id, sha, name, 40002)
        return _err(40002, f"parse failed: {e}", trace_id)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


@app.post("/v1/parse")
async def parse(file: UploadFile = File(...),
                trace_id: str | None = Form(default=None),
                x_trace_id: str | None = Header(default=None)):
    return await _handle(file, trace_id or x_trace_id or uuid.uuid4().hex)


@app.post("/parse")
async def parse_alias(file: UploadFile = File(...),
                      trace_id: str | None = Form(default=None),
                      x_trace_id: str | None = Header(default=None)):
    return await _handle(file, trace_id or x_trace_id or uuid.uuid4().hex)
