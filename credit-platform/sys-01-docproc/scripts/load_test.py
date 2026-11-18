"""T-01-09 压测：并发提交解析任务，输出 P50/P95 与错误率。"""
import argparse
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import requests


def one(url: str, path: str, trace: str):
    started = time.time()
    with open(path, "rb") as f:
        resp = requests.post(
            url, files={"file": (path.split("/")[-1], f)},
            data={"trace_id": trace}, timeout=1800,
        )
    return time.time() - started, resp.status_code


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--url", default="http://127.0.0.1:8102/v1/parse")
    ap.add_argument("--concurrency", type=int, default=5)
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument("--prefix", default="load")
    args = ap.parse_args()

    jobs = [
        (args.url, args.file, f"{args.prefix}-{r}-{i}")
        for r in range(args.rounds)
        for i in range(args.concurrency)
    ]
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        results = list(ex.map(lambda j: one(*j), jobs))

    lat = sorted(r[0] for r in results)
    errors = sum(1 for r in results if r[1] != 200)
    p50 = lat[len(lat) // 2]
    p95 = lat[min(len(lat) - 1, int(len(lat) * 0.95))]
    print(f"requests={len(lat)} concurrency={args.concurrency} errors={errors}")
    print(f"p50={p50:.1f}s p95={p95:.1f}s max={lat[-1]:.1f}s")
    print(f"rps={len(lat) / sum(lat):.3f}")


if __name__ == "__main__":
    main()
