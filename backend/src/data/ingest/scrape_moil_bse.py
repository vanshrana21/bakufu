"""
Scrape MOIL Limited's monthly production figures from BSE India.

MOIL (scrip 533286) files monthly production as a Regulation 30 press
release. The figure lives in the attached PDF, phrased like:

    "MOIL has recorded production of 1.63 lakh tonnes ... best ever November"

so the announcement list gives the filings, and each PDF gives one month.

Two BSE quirks this handles:
  - attachments live under AttachHis once they age out of AttachLive, and
    which one serves a given file is not predictable, so both are tried
  - the API needs a browser-ish session (User-Agent + Referer) or it
    returns an HTML error page with a 200

Rate limited to 1 request/second throughout.

Run: python -m src.data.ingest.scrape_moil_bse
"""

from __future__ import annotations

import io
import re
import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests
from pypdf import PdfReader
from sqlalchemy import text
from tqdm import tqdm

from src.config.settings import settings
from src.db.models import MoilMonthlyProduction
from src.db.session import SessionLocal, get_engine

SCRIP = "533286"
ANN_API = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"
ATTACH_BASES = (
    "https://www.bseindia.com/xml-data/corpfiling/AttachHis/",
    "https://www.bseindia.com/xml-data/corpfiling/AttachLive/",
)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

START_YEAR = 2010
REQUEST_DELAY_S = 1.0

#: Downloaded PDFs are cached as text so the parser can be improved
#: without hitting BSE again - the rate-limited download is the slow part.
PDF_CACHE: Path = settings.DATA_RAW / "moil" / "pdf_cache"

#: Announcements worth opening. MOIL's production releases are Reg-30 press
#: releases, so the subject line alone is not selective enough.
INTERESTING = re.compile(
    r"press release|production|performance|output|media release|achiev|record|"
    r"best[- ]ever|scales new|quantum jump",
    re.I,
)

#: "production of 1.63 lakh tonnes" / "production of 163000 tonnes"
PRODUCTION_RE = re.compile(
    r"production\s+of\s+([\d,]+(?:\.\d+)?)\s*(lakh\s+)?(?:tonnes?|MT)\b", re.I
)
#: The month the release is about, e.g. "best November Performance".
MONTH_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\b",
    re.I,
)
#: Cumulative statements must not be mistaken for a monthly figure. MOIL's
#: releases mix a monthly number with quarterly, half-year and FY-to-date
#: ones in the same paragraph, and the quarterly phrasings are what let three
#: ~4.4 lakh figures through on the first pass.
CUMULATIVE_HINT = re.compile(
    r"during\s+(the\s+)?first|FY\s*'?\d|year\s+to\s+date|cumulat|"
    r"quarter|Q[1-4]|half[- ]year|H[12]|financial\s+year|"
    r"since\s+inception|annual|nine\s+months|six\s+months|full\s+year",
    re.I,
)

#: A plausible MOIL month. Their best month on record is ~1.9 lakh tonnes, so
#: anything at or above 2.5 lakh is a quarter or a year, not a month.
MIN_MONTH_TONNES = 50_000
MAX_MONTH_TONNES = 250_000

MONTHS = {
    m: i
    for i, m in enumerate(
        [
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
        ],
        start=1,
    )
}


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.bseindia.com/corporates/ann.html",
        }
    )
    session.get("https://www.bseindia.com/", timeout=40)
    time.sleep(REQUEST_DELAY_S)
    return session


def fiscal_year(period: date) -> tuple[str, int]:
    """Indian FY runs April-March. Returns (label, quarter)."""
    start = period.year if period.month >= 4 else period.year - 1
    quarter = ((period.month - 4) % 12) // 3 + 1
    return f"FY{start}-{str(start + 1)[-2:]}", quarter


def list_announcements(session: requests.Session, year: int) -> list[dict]:
    """All announcements for one calendar year, paging until exhausted."""
    out: list[dict] = []
    for page in range(1, 20):
        try:
            response = session.get(
                ANN_API,
                params={
                    "pageno": page,
                    "strCat": "-1",
                    "strPrevDate": f"{year}0101",
                    "strScrip": SCRIP,
                    "strSearch": "P",
                    "strToDate": f"{year}1231",
                    "strType": "C",
                    "subcategory": "-1",
                },
                timeout=60,
            )
            time.sleep(REQUEST_DELAY_S)
            rows = response.json().get("Table") or []
        except Exception:  # noqa: BLE001 - a bad page must not kill the year
            break
        if not rows:
            break
        out.extend(rows)
        if len(rows) < 50:
            break
    return out


def fetch_pdf_text(session: requests.Session, attachment: str) -> str | None:
    """PDF text for one attachment, cached on disk, trying both BSE paths."""
    PDF_CACHE.mkdir(parents=True, exist_ok=True)
    cached = PDF_CACHE / f"{attachment}.txt"
    if cached.exists():
        return cached.read_text(encoding="utf-8", errors="replace") or None

    for base in ATTACH_BASES:
        try:
            response = session.get(base + attachment, timeout=90)
            time.sleep(REQUEST_DELAY_S)
        except Exception:  # noqa: BLE001
            continue
        if response.status_code != 200 or response.content[:4] != b"%PDF":
            continue
        try:
            reader = PdfReader(io.BytesIO(response.content))
            body = chr(10).join((page.extract_text() or "") for page in reader.pages)
        except Exception:  # noqa: BLE001 - unreadable PDF is a miss, not a crash
            continue
        # A scanned PDF extracts to near-nothing; cache the miss anyway so it
        # is not re-downloaded, and report it as unreadable upstream.
        cached.write_text(body, encoding="utf-8")
        return body or None
    return None

def parse_production(body: str, filed_on: date) -> tuple[date, float] | None:
    """(period_month, tonnes) from a press release body, or None.

    The first production figure in the release is the monthly one; later
    figures are fiscal-year-to-date. Sentences carrying a cumulative hint are
    skipped so an 11.80-lakh YTD number is never read as a month.
    """
    for match in PRODUCTION_RE.finditer(body):
        window = body[max(0, match.start() - 160) : match.start()]
        if CUMULATIVE_HINT.search(window):
            continue

        value = float(match.group(1).replace(",", ""))
        tonnes = value * 100_000 if match.group(2) else value
        if not (MIN_MONTH_TONNES <= tonnes <= MAX_MONTH_TONNES):
            continue

        # Month named near the figure, else the month before filing.
        head = body[: match.start() + 400]
        names = MONTH_RE.findall(head)
        if names:
            month = MONTHS[names[-1].lower()]
            year = filed_on.year
            if month > filed_on.month:
                year -= 1
            return date(year, month, 1), tonnes

        previous = filed_on.replace(day=1) - pd.Timedelta(days=1)
        return date(previous.year, previous.month, 1), tonnes
    return None


def scrape(start_year: int = START_YEAR) -> pd.DataFrame:
    session = make_session()
    end_year = date.today().year

    candidates: list[dict] = []
    for year in tqdm(range(start_year, end_year + 1), desc="years", unit="yr"):
        for row in list_announcements(session, year):
            subject = f"{row.get('NEWSSUB', '')} {row.get('HEADLINE', '')}"
            if not INTERESTING.search(subject):
                continue
            if not row.get("ATTACHMENTNAME"):
                continue
            candidates.append(row)

    print(f"\n  candidate announcements with attachments: {len(candidates)}")

    found: dict[date, dict] = {}
    misses = 0
    for row in tqdm(candidates, desc="pdfs", unit="pdf"):
        body = fetch_pdf_text(session, str(row["ATTACHMENTNAME"]))
        if not body:
            misses += 1
            continue
        filed_on = datetime.strptime(str(row["NEWS_DT"])[:10], "%Y-%m-%d").date()
        parsed = parse_production(body, filed_on)
        if parsed is None:
            continue
        period, tonnes = parsed
        # Keep the earliest filing for a period; later ones restate it.
        if period not in found or filed_on < found[period]["filing_date"]:
            found[period] = {
                "filing_date": filed_on,
                "period_month": period,
                "production_tonnes": tonnes,
                "source_url": f"https://www.bseindia.com/xml-data/corpfiling/AttachHis/{row['ATTACHMENTNAME']}",
                "source_type": "BSE_filing",
                "notes": str(row.get("HEADLINE") or "")[:400],
            }

    if not found:
        raise RuntimeError(
            "no monthly production figures parsed from BSE - the source may be "
            "blocked or the release wording may have changed"
        )

    frame = pd.DataFrame(sorted(found.values(), key=lambda r: r["period_month"]))
    labels = frame.period_month.map(lambda d: fiscal_year(d)[0])
    quarters = frame.period_month.map(lambda d: fiscal_year(d)[1])
    frame["fiscal_year"] = labels
    frame["fiscal_quarter"] = quarters

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE moil_monthly_production RESTART IDENTITY"))
    with SessionLocal() as session_db:
        session_db.bulk_insert_mappings(
            MoilMonthlyProduction, frame.to_dict(orient="records")
        )
        session_db.commit()

    span = pd.period_range(
        frame.period_month.min(), frame.period_month.max(), freq="M"
    )
    have = {pd.Period(p, freq="M") for p in frame.period_month}
    gaps = [str(p) for p in span if p not in have]

    print("")
    print("=" * 66)
    print("MOIL MONTHLY PRODUCTION")
    print("=" * 66)
    print(f"  months parsed   : {len(frame)}")
    print(f"  PDFs unreadable : {misses}")
    print(f"  date range      : {frame.period_month.min()} .. {frame.period_month.max()}")
    print(f"  span months     : {len(span)}  ->  gaps: {len(gaps)}")
    print(f"  tonnes range    : {frame.production_tonnes.min():,.0f} .. {frame.production_tonnes.max():,.0f}")
    print(f"  mean month      : {frame.production_tonnes.mean():,.0f} t")
    if gaps:
        print(f"  missing periods : {', '.join(gaps[:24])}{' ...' if len(gaps) > 24 else ''}")

    return frame


def main() -> None:
    scrape()


if __name__ == "__main__":
    main()
