"""
Bulk-download the IBM Monthly Statistics of Mineral Production (MSMP) bulletins.

The Indian Bureau of Mines publishes one PDF per month covering all minerals
and all states. Those bulletins carry state-level manganese ore production,
which is our proxy for MOIL's operating region - MOIL does not publish its own
monthly figures anywhere public.

The archive CSV lists 134 rows: 126 that parse as "%b %Y" and 8 supplement or
corrigendum rows. Two of the 126 are the same month:

    Mar 2021  MSMP_March2021_final release.pdf    <- final
    Mar 2021  MSMP_Mar_21_advance release.pdf     <- superseded

Both map to the same output filename, and the superseded one sorts second in
the CSV, so without the drop below the provisional figures would silently win.
Everything dropped is written to supplements_skipped.csv with a reason rather
than being discarded quietly.

Rate limited to 2s between requests, backing off to 10s for the remainder of
the batch if the server ever answers 429.

Run: python -m src.data.ingest.download_msmp_archive
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import pandas as pd
import requests

from src.config.settings import settings

MOIL_RAW: Path = settings.DATA_RAW / "moil"
ARCHIVE_CSV: Path = MOIL_RAW / "msmp_archive_full.csv"
PDF_DIR: Path = MOIL_RAW / "msmp_pdfs"
DOWNLOAD_LOG: Path = MOIL_RAW / "download_log.csv"
SKIPPED_LOG: Path = MOIL_RAW / "supplements_skipped.csv"

#: A real bulletin is a few hundred KB at minimum; anything under this is a
#: truncated response or an error page that happened to start with %PDF.
MIN_PDF_BYTES = 10 * 1024

POLITE_DELAY = 2.0
THROTTLED_DELAY = 10.0  # adopted for the rest of the run after any 429
MAX_RETRIES = 3
TIMEOUT = 60

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "Accept": "application/pdf,*/*",
}


def encode_url(url: str) -> str:
    """Percent-encode the path so filenames containing spaces resolve.

    Several 2017-2022 filenames have literal spaces ("MSMP_FEB 2017.pdf").
    """
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path=quote(parts.path, safe="/%")))


def load_archive() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split the archive into downloadable months and everything skipped."""
    frame = pd.read_csv(ARCHIVE_CSV)
    frame["notes"] = frame["notes"].fillna("")

    def parse_month(value: object) -> pd.Timestamp | None:
        try:
            return pd.Timestamp(datetime.strptime(str(value).strip(), "%b %Y"))
        except ValueError:
            return None

    frame["month"] = frame["report_month"].map(parse_month)

    supplements = frame[frame["month"].isna()].copy()
    supplements["reason"] = "supplement_or_corrigendum"

    monthly = frame[frame["month"].notna()].copy()
    # Match "superseded" alone, never "advance release": the *final* rows also
    # mention an advance release ("Final release (an Advance Release also
    # exists for this month)"), so matching that phrase drops four real months.
    superseded_mask = monthly["notes"].str.contains("superseded", case=False, regex=False)
    superseded = monthly[superseded_mask].copy()
    superseded["reason"] = "superseded_advance_release"

    keep = monthly[~superseded_mask].copy()
    keep = keep.sort_values("month").reset_index(drop=True)

    skipped = pd.concat([supplements, superseded], ignore_index=True)
    return keep, skipped


def target_path(month: pd.Timestamp) -> Path:
    return PDF_DIR / f"MSMP_{month.year}_{month.month:02d}.pdf"


def fetch(session: requests.Session, url: str, delay: float) -> tuple[bytes | None, str, float]:
    """Return (content, status, delay). `delay` may be raised by a 429."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(encode_url(url), timeout=TIMEOUT, headers=HEADERS)
        except requests.Timeout:
            if attempt == MAX_RETRIES:
                return None, "failed_timeout", delay
            time.sleep(delay * (2 ** (attempt - 1)))
            continue
        except requests.RequestException as exc:
            if attempt == MAX_RETRIES:
                return None, f"failed_request_{type(exc).__name__}", delay
            time.sleep(delay * (2 ** (attempt - 1)))
            continue

        if response.status_code == 429:
            # Slow the whole batch down, not just this request.
            delay = THROTTLED_DELAY
            if attempt == MAX_RETRIES:
                return None, "failed_429", delay
            time.sleep(THROTTLED_DELAY * attempt)
            continue

        if 500 <= response.status_code < 600:
            if attempt == MAX_RETRIES:
                return None, f"failed_http_{response.status_code}", delay
            time.sleep(delay * (2 ** (attempt - 1)))
            continue

        if response.status_code != 200:
            return None, f"failed_http_{response.status_code}", delay

        body = response.content
        # IBM serves an HTML error page with a 200 for missing files.
        if not body.startswith(b"%PDF"):
            return None, "failed_not_pdf", delay
        if len(body) < MIN_PDF_BYTES:
            return None, "failed_too_small", delay
        return body, "ok", delay

    return None, "failed_exhausted", delay


def download_all(limit: int | None = None, force: bool = False) -> pd.DataFrame:
    PDF_DIR.mkdir(parents=True, exist_ok=True)

    keep, skipped = load_archive()
    skipped.drop(columns=["month"]).to_csv(SKIPPED_LOG, index=False)
    print(f"  skipped rows logged    : {len(skipped)} -> {SKIPPED_LOG.name}")

    if limit:
        keep = keep.head(limit)

    session = requests.Session()
    delay = POLITE_DELAY
    log: list[dict[str, object]] = []
    counts = {"ok": 0, "skipped_existing": 0, "failed": 0}
    total_bytes = 0

    for position, row in enumerate(keep.itertuples(), start=1):
        month: pd.Timestamp = row.month
        destination = target_path(month)

        if not force and destination.exists() and destination.stat().st_size > MIN_PDF_BYTES:
            counts["skipped_existing"] += 1
            payload = destination.read_bytes()
            total_bytes += len(payload)
            log.append(
                {
                    "report_month": month.strftime("%Y-%m"),
                    "url": row.pdf_url,
                    "status": "skipped_existing",
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "downloaded_at": "",
                }
            )
            continue

        body, status, delay = fetch(session, row.pdf_url, delay)
        if body is None:
            counts["failed"] += 1
            print(f"    FAILED {month.strftime('%Y-%m')}  {status}  {row.pdf_url}")
            log.append(
                {
                    "report_month": month.strftime("%Y-%m"),
                    "url": row.pdf_url,
                    "status": status,
                    "bytes": 0,
                    "sha256": "",
                    "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
            )
        else:
            destination.write_bytes(body)
            counts["ok"] += 1
            total_bytes += len(body)
            log.append(
                {
                    "report_month": month.strftime("%Y-%m"),
                    "url": row.pdf_url,
                    "status": "ok",
                    "bytes": len(body),
                    "sha256": hashlib.sha256(body).hexdigest(),
                    "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
            )

        if position % 20 == 0:
            print(
                f"    {position}/{len(keep)}  ok={counts['ok']} "
                f"failed={counts['failed']} skipped={counts['skipped_existing']}"
            )
        time.sleep(delay)

    frame = pd.DataFrame(log)
    frame.to_csv(DOWNLOAD_LOG, index=False, quoting=csv.QUOTE_MINIMAL)

    print()
    print("=" * 70)
    print("MSMP DOWNLOAD SUMMARY")
    print("=" * 70)
    print(f"  attempted        : {len(keep)}")
    print(f"  succeeded        : {counts['ok']}")
    print(f"  failed           : {counts['failed']}")
    print(f"  skipped existing : {counts['skipped_existing']}")
    print(f"  total size       : {total_bytes / 1e6:,.1f} MB")
    print(f"  rate limit ended at {delay:.0f}s between requests")
    print(f"  log   -> {DOWNLOAD_LOG}")
    print(f"  pdfs  -> {PDF_DIR}")
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="only the first N months")
    parser.add_argument("--force", action="store_true", help="re-download existing files")
    args = parser.parse_args()
    download_all(limit=args.limit, force=args.force)


if __name__ == "__main__":
    main()
