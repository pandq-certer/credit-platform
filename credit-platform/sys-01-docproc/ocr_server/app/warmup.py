"""镜像构建期预热：下载 PP-OCRv5 模型并输出 sha256 清单。"""
import hashlib
import os
import pathlib

from paddleocr import PaddleOCR

cache = os.environ.get("PADDLE_PDX_CACHE_HOME", "/models")
os.makedirs(cache, exist_ok=True)

ocr = PaddleOCR(
    lang="ch",
    ocr_version="PP-OCRv5",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=True,
)
print("warmup ok", type(ocr).__name__)

manifest = pathlib.Path("/models/model-sha256.txt")
lines = []
for p in sorted(pathlib.Path(cache).rglob("*")):
    if p.is_file() and p.stat().st_size > 1024 * 1024:
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        lines.append(f"{h}  {p}")
manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"wrote {manifest} ({len(lines)} files)")
