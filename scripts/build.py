#!/usr/bin/env python3
"""Reproduce the 2026-10 top-1m CrUX subset for the 12 selected TLDs."""

import argparse
import csv
import gzip
import hashlib
import shutil
import tempfile
import urllib.request
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

SNAPSHOT = "202610"
SOURCE_URL = (
    "https://raw.githubusercontent.com/zakird/crux-top-lists/"
    f"main/data/global/{SNAPSHOT}.csv.gz"
)
SOURCE_SHA256 = "410165bb4a6bdb735adbb0d317280dff21ad7555ea35016d0ae8d72c5ad14911"
EXPECTED = {
    "com": 414049,
    "net": 30408,
    "org": 25825,
    "co": 9903,
    "io": 6308,
    "online": 5811,
    "app": 4917,
    "xyz": 4632,
    "me": 2975,
    "ai": 2904,
    "pro": 2224,
    "gg": 1006,
}


def sha256_file(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def build(source: Path, target_dir: Path) -> None:
    digest = sha256_file(source)
    if digest != SOURCE_SHA256:
        raise ValueError(f"Unexpected source SHA-256: {digest}")
    target_dir.mkdir(parents=True, exist_ok=True)
    counts = Counter()
    rows_seen = 0
    top1000 = 0
    csv_path = target_dir / f"{SNAPSHOT}.csv"
    top_path = target_dir / "top-1000.csv"

    with (
        gzip.open(source, "rt", encoding="utf-8", newline="") as input_file,
        csv_path.open("w", encoding="utf-8", newline="") as output_file,
        top_path.open("w", encoding="utf-8", newline="") as top_file,
    ):
        reader = csv.DictReader(input_file)
        if reader.fieldnames != ["origin", "rank"]:
            raise ValueError(f"Unexpected input columns: {reader.fieldnames}")
        writer = csv.DictWriter(output_file, fieldnames=["origin", "rank"], lineterminator="\n")
        sample = csv.DictWriter(top_file, fieldnames=["origin", "rank"], lineterminator="\n")
        writer.writeheader()
        sample.writeheader()

        for row in reader:
            rows_seen += 1
            hostname = urlsplit(row["origin"]).hostname
            if not hostname:
                continue
            tld = hostname.rsplit(".", 1)[-1].lower()
            if tld not in EXPECTED:
                continue
            writer.writerow({"origin": row["origin"], "rank": row["rank"]})
            counts[tld] += 1
            if row["rank"] == "1000":
                sample.writerow({"origin": row["origin"], "rank": row["rank"]})
                top1000 += 1

    if rows_seen != 1_000_000 or counts != Counter(EXPECTED) or top1000 != 593:
        raise ValueError(f"Unexpected counts: input={rows_seen}, selected={sum(counts.values())}, top1000={top1000}, tlds={counts}")

    with (target_dir / "tld-counts.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["tld", "count"])
        for tld, count in EXPECTED.items():
            writer.writerow([f".{tld}", count])

    with (target_dir / f"{SNAPSHOT}.csv.gz").open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0, compresslevel=9) as gz:
            with csv_path.open("rb") as csv_input:
                shutil.copyfileobj(csv_input, gz)

    print(f"OK: {rows_seen:,} input rows, {sum(counts.values()):,} kept, {top1000} top-1000 records.")
    for file in target_dir.iterdir():
        if file.is_file():
            print(f"  {file.name}: {file.stat().st_size:,} bytes")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=None, help="Local gzip snapshot (optional)")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    args = parser.parse_args()
    if args.source:
        build(args.source, args.output_dir)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / f"{SNAPSHOT}.csv.gz"
            request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "top-1m-websites/1.0"})
            with urllib.request.urlopen(request, timeout=120) as response, path.open("wb") as out:
                shutil.copyfileobj(response, out)
            build(path, args.output_dir)


if __name__ == "__main__":
    main()
