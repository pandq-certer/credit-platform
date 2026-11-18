"""docling 外部 OCR 适配器（T-01-04 关键自研项）。

docling 关闭内置 OCR 后不会自动调用外部服务；本插件实现 docling 的
BaseOcrModel，通过 HTTP 调 8101 /ocr，把统一契约 blocks 回填为 TextCell。
"""
import io
import logging
from collections.abc import Iterable
from pathlib import Path
from typing import ClassVar, List, Optional, Type

import requests
from docling_core.types.doc import BoundingBox, CoordOrigin
from docling_core.types.doc.page import BoundingRectangle, TextCell

from docling.datamodel.accelerator_options import AcceleratorOptions
from docling.datamodel.base_models import (
    DoclingComponentType,
    ErrorItem,
    FailureCategory,
    Page,
)
from docling.datamodel.document import ConversionResult
from docling.datamodel.pipeline_options import OcrMode, OcrOptions
from docling.models.base_ocr_model import BaseOcrModel
from docling.utils.profiling import TimeRecorder

_log = logging.getLogger(__name__)


class OcrServiceError(RuntimeError):
    def __init__(self, code: int, message: str, reasons=None):
        super().__init__(message)
        self.code = code
        self.reasons = reasons or []


def ocr_engines():
    """docling 插件入口：注册自研外部 OCR 引擎。"""
    return {"ocr_engines": [PaddleOcrHttpModel]}


class PaddleOcrHttpOptions(OcrOptions):
    kind: ClassVar[str] = "paddleocr_http"
    lang: List[str] = ["ch"]
    base_url: str = "http://127.0.0.1:8101"
    timeout: float = 180.0
    mode: OcrMode = OcrMode.FULL_PAGE


class PaddleOcrHttpModel(BaseOcrModel):
    def __init__(
        self,
        *,
        enabled: bool,
        artifacts_path: Optional[Path],
        options: PaddleOcrHttpOptions,
        accelerator_options: AcceleratorOptions,
    ):
        super().__init__(
            enabled=enabled,
            artifacts_path=artifacts_path,
            options=options,
            accelerator_options=accelerator_options,
        )
        self.options: PaddleOcrHttpOptions
        self._session = requests.Session()
        self.last_page_quality: dict[int, float] = {}

    @classmethod
    def get_options_type(cls) -> Type[OcrOptions]:
        return PaddleOcrHttpOptions

    def _post_image(self, png: bytes, trace_id: str) -> dict:
        resp = self._session.post(
            f"{self.options.base_url.rstrip('/')}/ocr",
            files={"file": ("page.png", png, "image/png")},
            headers={"X-Trace-Id": trace_id},
            timeout=self.options.timeout,
        )
        if resp.status_code != 200:
            try:
                body = resp.json()
            except Exception:  # noqa: BLE001
                body = {}
            raise OcrServiceError(
                int(body.get("error_code", 40002)),
                body.get("message", resp.text[:300]),
                body.get("refuse_reasons"),
            )
        return resp.json()

    def _to_cells(self, blocks: list, rect: BoundingBox) -> List[TextCell]:
        cells: List[TextCell] = []
        # docling-core 版本差异：width/height/area 在部分版本是属性而非方法
        w = rect.width() if callable(rect.width) else rect.width
        h = rect.height() if callable(rect.height) else rect.height
        for idx, b in enumerate(blocks):
            x1, y1, x2, y2 = b["bbox"]
            bbox = BoundingBox.from_tuple(
                coord=(
                    rect.l + x1 * w,
                    rect.t + y1 * h,
                    rect.l + x2 * w,
                    rect.t + y2 * h,
                ),
                origin=CoordOrigin.TOPLEFT,
            )
            text = str(b.get("text", ""))
            cells.append(
                TextCell(
                    index=idx,
                    text=text,
                    orig=text,
                    confidence=float(b.get("confidence", 1.0)),
                    from_ocr=True,
                    rect=BoundingRectangle.from_bounding_box(bbox),
                )
            )
        return cells

    def __call__(
        self, conv_res: ConversionResult, page_batch: Iterable[Page]
    ) -> Iterable[Page]:
        if not self.enabled:
            yield from page_batch
            return

        trace_id = getattr(conv_res, "input", None)
        trace_id = getattr(trace_id, "file", None)
        trace_id = str(trace_id) if trace_id else "docling"

        for page in page_batch:
            if page._backend is None or not page._backend.is_valid():
                yield page
                continue

            with TimeRecorder(conv_res, "ocr"):
                ocr_rects = self.get_ocr_rects(page)
                cells: List[TextCell] = []
                for rect in ocr_rects:
                    area = rect.area() if callable(rect.area) else rect.area
                    if area == 0:
                        continue
                    image = page._backend.get_page_image(
                        scale=self.options.scale, cropbox=rect
                    )
                    buf = io.BytesIO()
                    image.save(buf, format="PNG")
                    try:
                        data = self._post_image(buf.getvalue(), trace_id)
                    except OcrServiceError:
                        raise
                    except Exception as e:  # noqa: BLE001
                        _log.error("external OCR failed page=%s: %s", page.page_no, e)
                        conv_res.errors.append(
                            ErrorItem(
                                component_type=DoclingComponentType.MODEL,
                                module_name=type(self).__name__,
                                error_message=str(e) or e.__class__.__name__,
                                category=FailureCategory.INFERENCE_FAILURE,
                                page_no=page.page_no,
                            )
                        )
                        continue
                    self.last_page_quality[page.page_no] = float(
                        data.get("quality", {}).get("score", 0.0)
                    )
                    cells.extend(self._to_cells(data.get("blocks", []), rect))

                self.post_process_cells(cells, page, conv_res)

            yield page
