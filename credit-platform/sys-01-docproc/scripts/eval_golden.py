"""V-01-05 金标评测：逐页调用 8102 解析，与人工校对稿比对字符准确率。"""
import csv
import io
import os
import re
import sys

import requests
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN = os.path.join(ROOT, "golden")
PARSE_URL = os.environ.get("SYS01_PARSE_URL", "http://127.0.0.1:8102/v1/parse")


def normalize(text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)  # 图片
    text = re.sub(r"[#*`>\-|]", "", text)
    return re.sub(r"\s+", "", text)


def edit_distance(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def main() -> int:
    manifest = os.path.join(GOLDEN, "manifest.csv")
    rows = list(csv.DictReader(open(manifest, encoding="utf-8")))
    total_chars = 0
    weighted = 0.0
    plausible = 0
    for row in rows:
        page = os.path.join(GOLDEN, row["page_file"])
        ref_path = os.path.join(GOLDEN, row["transcript_file"])
        if not (os.path.exists(page) and os.path.exists(ref_path)):
            continue
        plausible += 1
        ext = os.path.splitext(page)[1].lower()
        if ext in (".jpg", ".jpeg", ".png"):
            buf = io.BytesIO()
            Image.open(page).convert("RGB").save(buf, format="PDF", resolution=300.0)
            buf.seek(0)
            resp = requests.post(
                PARSE_URL, files={"file": (os.path.basename(page) + ".pdf", buf)},
                timeout=600,
            )
        else:
            with open(page, "rb") as f:
                resp = requests.post(
                    PARSE_URL, files={"file": (os.path.basename(page), f)}, timeout=600
                )
        if resp.status_code != 200:
            print(f"{row['page_file']}: parse failed {resp.status_code} {resp.text[:100]}")
            continue
        hyp = normalize(resp.json().get("markdown", ""))
        ref = normalize(open(ref_path, encoding="utf-8").read())
        dist = edit_distance(hyp, ref)
        acc = max(0.0, 1 - dist / max(len(ref), 1))
        total_chars += len(ref)
        weighted += acc * len(ref)
        print(f"{row['page_file']}: chars={len(ref)} acc={acc:.4f}")

    if plausible < 20:
        print(f"BLOCKED: only {plausible}/20 golden pages available with transcripts")
        return 2
    mean = weighted / max(total_chars, 1)
    print(f"weighted_char_accuracy={mean:.4f} threshold=0.98 -> {'PASS' if mean >= 0.98 else 'FAIL'}")
    return 0 if mean >= 0.98 else 1


if __name__ == "__main__":
    sys.exit(main())
