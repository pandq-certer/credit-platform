import json
import logging
import os

import psycopg

log = logging.getLogger("db")

DSN = os.environ.get(
    "SYS01_DB_DSN",
    "postgresql://credit_sys01:credit_sys01@127.0.0.1:5432/credit_sys01",
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS parse_task (
  trace_id     text PRIMARY KEY,
  file_sha256  text NOT NULL,
  filename     text,
  format       text,
  page_count   int,
  status       text,
  error_code   int,
  created_at   timestamptz DEFAULT now()
);
CREATE TABLE IF NOT EXISTS doc_page (
  trace_id text NOT NULL,
  page     int NOT NULL,
  width    double precision,
  height   double precision,
  PRIMARY KEY (trace_id, page)
);
CREATE TABLE IF NOT EXISTS doc_block (
  block_id   text PRIMARY KEY,
  trace_id   text NOT NULL,
  page       int NOT NULL,
  block_type text,
  text       text,
  bbox       double precision[],
  polygon    double precision[][],
  confidence double precision,
  parser     text
);
CREATE INDEX IF NOT EXISTS idx_doc_block_trace ON doc_block(trace_id);
CREATE TABLE IF NOT EXISTS doc_table (
  table_id text PRIMARY KEY,
  trace_id text NOT NULL,
  page     int,
  pages    int[],
  rows     int,
  cols     int,
  cells    jsonb,
  markdown text,
  bbox     double precision[]
);
CREATE TABLE IF NOT EXISTS doc_image (
  image_id text PRIMARY KEY,
  trace_id text NOT NULL,
  page     int,
  bbox     double precision[],
  caption  text
);
CREATE TABLE IF NOT EXISTS quality_review (
  id         bigserial PRIMARY KEY,
  trace_id   text NOT NULL,
  block_id   text NOT NULL,
  page       int,
  confidence double precision,
  status     text DEFAULT 'pending',
  created_at timestamptz DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_quality_review_trace_block
  ON quality_review(trace_id, block_id);
"""


def connect():
    return psycopg.connect(DSN, autocommit=True)


def init_schema() -> None:
    with connect() as conn:
        conn.execute(SCHEMA)
    log.info("schema ready")


def save_result(r: dict, status: str = "success") -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO parse_task(trace_id,file_sha256,filename,format,page_count,status)
               VALUES (%s,%s,%s,%s,%s,%s)
               ON CONFLICT (trace_id) DO UPDATE SET
                 file_sha256=EXCLUDED.file_sha256, filename=EXCLUDED.filename,
                 format=EXCLUDED.format, page_count=EXCLUDED.page_count,
                 status=EXCLUDED.status, error_code=NULL""",
            (r["trace_id"], r["file_sha256"], r["filename"], r["format"],
             r["page_count"], status),
        )
        for page, size in r["page_sizes"].items():
            conn.execute(
                """INSERT INTO doc_page(trace_id,page,width,height) VALUES (%s,%s,%s,%s)
                   ON CONFLICT (trace_id,page) DO UPDATE
                   SET width=EXCLUDED.width, height=EXCLUDED.height""",
                (r["trace_id"], page, size["width"], size["height"]),
            )
        for b in r["blocks"]:
            conn.execute(
                """INSERT INTO doc_block(block_id,trace_id,page,block_type,text,bbox,polygon,confidence,parser)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (block_id) DO UPDATE SET text=EXCLUDED.text""",
                (b["block_id"], r["trace_id"], b["page"], b["type"], b["text"],
                 b["bbox"], b["polygon"], b["confidence"], b["parser"]),
            )
        for t in r["tables"]:
            conn.execute(
                """INSERT INTO doc_table(table_id,trace_id,page,pages,rows,cols,cells,markdown,bbox)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (table_id) DO UPDATE SET cells=EXCLUDED.cells""",
                (t["table_id"], r["trace_id"], t["page"], t["pages"], t["rows"],
                 t["cols"], json.dumps(t["cells"], ensure_ascii=False), t["markdown"], t["bbox"]),
            )
        for i in r["images"]:
            conn.execute(
                """INSERT INTO doc_image(image_id,trace_id,page,bbox,caption)
                   VALUES (%s,%s,%s,%s,%s)
                   ON CONFLICT (image_id) DO UPDATE SET caption=EXCLUDED.caption""",
                (i["image_id"], r["trace_id"], i["page"], i["bbox"], i["caption"]),
            )
        for q in r.get("quality_review", []):
            conn.execute(
                """INSERT INTO quality_review(trace_id,block_id,page,confidence)
                   VALUES (%s,%s,%s,%s)
                   ON CONFLICT (trace_id,block_id) DO NOTHING""",
                (r["trace_id"], q["block_id"], q["page"], q["confidence"]),
            )


def save_failure(trace_id: str, sha: str, filename: str, error_code: int) -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO parse_task(trace_id,file_sha256,filename,status,error_code)
               VALUES (%s,%s,%s,'failed',%s)
               ON CONFLICT (trace_id) DO UPDATE SET status='failed', error_code=EXCLUDED.error_code""",
            (trace_id, sha, filename, error_code),
        )


def list_reviews(status: str = "pending", limit: int = 100) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """SELECT id, trace_id, block_id, page, confidence, status, created_at
               FROM quality_review WHERE status=%s ORDER BY id DESC LIMIT %s""",
            (status, limit),
        ).fetchall()
    return [
        {
            "id": r[0], "trace_id": r[1], "block_id": r[2], "page": r[3],
            "confidence": r[4], "status": r[5], "created_at": r[6].isoformat(),
        }
        for r in rows
    ]


def update_review(review_id: int, status: str) -> bool:
    with connect() as conn:
        cur = conn.execute(
            "UPDATE quality_review SET status=%s WHERE id=%s", (status, review_id)
        )
        return cur.rowcount > 0
