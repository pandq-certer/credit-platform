import hashlib
import io
import logging
import threading
import time
from typing import Any

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import (
    PictureItem,
    TableItem,
    TextItem,
)

from .ocr_plugin import PaddleOcrHttpOptions

log = logging.getLogger("parse")

FORMAT_MAP = {
    ".pdf": InputFormat.PDF,
    ".docx": InputFormat.DOCX,
    ".html": InputFormat.HTML,
    ".htm": InputFormat.HTML,
    ".xlsx": InputFormat.XLSX,
}

_convert_lock = threading.Lock()
_converter: DocumentConverter | None = None


def get_converter(ocr_base_url: str) -> DocumentConverter:
    global _converter
    if _converter is not None:
        return _converter

    opts = PdfPipelineOptions()
    opts.do_ocr = True                      # 打开，但引擎指向自研 paddleocr_http 适配器
    opts.ocr_options = PaddleOcrHttpOptions(base_url=ocr_base_url)
    opts.allow_external_plugins = True       # 允许非 docling.* 的 OCR 插件
    opts.do_table_structure = True
    opts.table_structure_options.do_cell_matching = True
    opts.images_scale = 2.0
    opts.generate_parsed_pages = True        # 供质量抽检读取 OCR 置信度

    _converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
    )
    return _converter


def _bbox_norm(bbox, page_size):
    w, h = page_size
    if bbox is None or w <= 0 or h <= 0:
        return [0.0, 0.0, 0.0, 0.0], [[0.0, 0.0]] * 4
    x1 = max(0.0, min(1.0, bbox.l / w))
    y1 = max(0.0, min(1.0, bbox.t / h))
    x2 = max(0.0, min(1.0, bbox.r / w))
    y2 = max(0.0, min(1.0, bbox.b / h))
    return (
        [round(x1, 6), round(y1, 6), round(x2, 6), round(y2, 6)],
        [[round(x1, 6), round(y1, 6)], [round(x2, 6), round(y1, 6)],
         [round(x2, 6), round(y2, 6)], [round(x1, 6), round(y2, 6)]],
    )


def _table_matrix(table: TableItem):
    grid = table.data.grid
    return [[c.text for c in row] for row in grid]


def _merge_cross_page_tables(tables: list[dict]) -> list[dict]:
    """跨页合并：列数一致且表头相同的相邻表拼接（T-01-07）。"""
    merged: list[dict] = []
    for t in tables:
        if merged:
            prev = merged[-1]
            same_cols = prev["cols"] == t["cols"] and t["cols"] > 0
            same_header = (
                same_cols
                and prev["cells"]
                and t["cells"]
                and prev["cells"][0] == t["cells"][0]
            )
            if same_header and t["page"] in (prev["pages"][-1], prev["pages"][-1] + 1):
                prev["cells"].extend(t["cells"][1:])
                prev["rows"] = len(prev["cells"])
                prev["pages"].append(t["page"])
                prev["merged_across_pages"] = True
                continue
        merged.append(t)
    return merged


def parse_file(path, filename: str, trace_id: str, ocr_base_url: str) -> dict[str, Any]:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in FORMAT_MAP:
        raise ValueError("unsupported format")

    converter = get_converter(ocr_base_url)
    started = time.time()
    with _convert_lock:
        result = converter.convert(path)
    doc = result.document

    page_sizes: dict[int, tuple[float, float]] = {}
    for p in result.pages:
        page_sizes[p.page_no] = (float(p.size.width), float(p.size.height))

    sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
    blocks: list[dict] = []
    tables: list[dict] = []
    images: list[dict] = []
    seq = 0

    for item, _level in doc.iterate_items():
        prov = item.prov[0] if getattr(item, "prov", None) else None
        page_no = int(prov.page_no) if prov is not None else 1
        size = page_sizes.get(page_no, (0.0, 0.0))
        bbox, polygon = _bbox_norm(getattr(prov, "bbox", None), size)

        if isinstance(item, TableItem):
            cells = _table_matrix(item)
            tables.append(
                {
                    "table_id": f"{sha}-p{page_no}-t{len(tables) + 1:03d}",
                    "page": page_no,
                    "pages": [page_no],
                    "rows": len(cells),
                    "cols": len(cells[0]) if cells else 0,
                    "cells": cells,
                    "markdown": item.export_to_markdown(doc),
                    "bbox": bbox,
                }
            )
            continue

        if isinstance(item, PictureItem):
            images.append(
                {
                    "image_id": f"{sha}-p{page_no}-i{len(images) + 1:03d}",
                    "page": page_no,
                    "bbox": bbox,
                    "caption": (item.caption_text(doc) or "")[:500],
                }
            )
            continue

        if isinstance(item, TextItem) and item.text.strip():
            seq += 1
            blocks.append(
                {
                    "block_id": f"{sha}-p{page_no}-{seq:04d}",
                    "page": page_no,
                    "type": str(item.label),
                    "text": item.text,
                    "bbox": bbox,
                    "polygon": polygon,
                    "confidence": 1.0,
                    "parser": "docling-2.150.1",
                    "trace_id": trace_id,
                }
            )

    tables = _merge_cross_page_tables(tables)

    queue = []
    for p in result.pages:
        parsed = getattr(p, "parsed_page", None)
        cells = getattr(parsed, "textline_cells", None) or []
        confs = [
            float(c.confidence)
            for c in cells
            if getattr(c, "from_ocr", False) and getattr(c, "confidence", None) is not None
        ]
        if confs and min(confs) < 0.8:
            queue.append(
                {
                    "block_id": f"{sha}-p{p.page_no}-qc",
                    "page": int(p.page_no),
                    "confidence": min(confs),
                }
            )

    return {
        "trace_id": trace_id,
        "file_sha256": sha,
        "filename": filename,
        "format": ext.lstrip("."),
        "page_count": len(result.pages),
        "markdown": doc.export_to_markdown(),
        "blocks": blocks,
        "tables": tables,
        "images": images,
        "quality_review": queue,
        "page_sizes": {k: {"width": v[0], "height": v[1]} for k, v in page_sizes.items()},
        "metrics": {"duration_ms": int((time.time() - started) * 1000)},
    }
