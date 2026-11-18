"""T-01-07 表格结构评测：代表性复杂表格（跨页 / 合并表头 / 多列财务表）。"""
import csv
import io
import os
import sys
from difflib import SequenceMatcher

import requests
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN = os.path.join(ROOT, "golden")
PARSE_URL = os.environ.get("SYS01_PARSE_URL", "http://127.0.0.1:8102/v1/parse")

CASES = [
    {"name": "跨页续表(10+11)", "scans": ["page-010.jpg", "page-011.jpg"],
     "csv": "page-010-011-merged.csv"},
    {"name": "合并表头(15)", "scans": ["page-015.jpg"], "csv": "page-015.csv"},
    {"name": "财务多列表(6)", "scans": ["page-006.jpg"], "csv": "page-006.csv"},
    {"name": "税务多列表(7)", "scans": ["page-007.jpg"], "csv": "page-007.csv"},
]


def norm(s):
    return "".join(str(s).split())


def flat(rows):
    return norm("".join(norm(c) for row in rows for c in row))


def parse(scans):
    buf = io.BytesIO()
    images = [Image.open(os.path.join(GOLDEN, "scans", s)).convert("RGB") for s in scans]
    images[0].save(buf, format="PDF", resolution=300.0, save_all=True,
                   append_images=images[1:])
    buf.seek(0)
    resp = requests.post(
        PARSE_URL, files={"file": ("table-case.pdf", buf)}, timeout=900
    )
    resp.raise_for_status()
    return resp.json()


def main():
    scores = []
    for case in CASES:
        expected = list(csv.reader(open(os.path.join(GOLDEN, "tables", case["csv"]),
                                        encoding="utf-8")))
        result = parse(case["scans"])
        tables = result.get("tables", [])
        if not tables:
            print(f"{case['name']}: NO TABLE -> score 0")
            scores.append(0.0)
            continue
        exp_txt = flat(expected)
        best, best_sim = None, -1.0
        for t in tables:
            sim = SequenceMatcher(None, flat(t["cells"]), exp_txt).ratio()
            if sim > best_sim:
                best, best_sim = t, sim
        rows = len(expected)
        cols = len(expected[0]) if expected else 0
        shape_ok = 1.0 if (best["rows"] == rows and best["cols"] == cols) else 0.0
        score = 0.5 * shape_ok + 0.5 * best_sim
        scores.append(score)
        print(
            f"{case['name']}: expected {rows}x{cols} got {best['rows']}x{best['cols']} "
            f"shape={shape_ok} text_sim={best_sim:.4f} score={score:.4f}"
        )

    mean = sum(scores) / len(scores)
    print(f"mean_table_score={mean:.4f} threshold=0.90 -> {'PASS' if mean >= 0.90 else 'FAIL'}")
    return 0 if mean >= 0.90 else 1


if __name__ == "__main__":
    sys.exit(main())
