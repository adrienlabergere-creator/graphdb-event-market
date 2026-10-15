"""Helpers shared by the ingestion scripts: batching, cached downloads, date parsing."""

from __future__ import annotations

import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Iterator

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
BATCH_SIZE = 500
USER_AGENT = "graphdb-course-project/1.0 (educational use)"


def chunked(items: Iterable[dict], size: int = BATCH_SIZE) -> Iterator[list[dict]]:
    """Yield lists of at most `size` items."""
    batch: list[dict] = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def run_batches(session, query: str, rows: Iterable[dict], size: int = BATCH_SIZE, **params) -> int:
    """Run an UNWIND query once per batch of rows. The query must read the batch from `$rows`. Returns the row count."""
    total = 0
    for batch in chunked(rows, size):
        session.run(query, rows=batch, **params).consume()
        total += len(batch)
    return total


def parse_day(text: str) -> date:
    """Parse a YYYY-MM-DD string."""
    return datetime.strptime(text, "%Y-%m-%d").date()


def days_between(start: date, end: date, step: int = 1) -> list[date]:
    """Every `step`-th day from start to end, both included."""
    out, current = [], start
    while current <= end:
        out.append(current)
        current += timedelta(days=step)
    return out


def download(url: str, target: Path, timeout: int = 60) -> Path:
    """Download a URL to `target` unless the file already exists (cache). Returns the path."""
    if target.exists() and target.stat().st_size > 0:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310 - fixed public URLs
        target.write_bytes(response.read())
    return target
