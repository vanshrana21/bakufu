"""
Extract monthly manganese ore production from the IBM MSMP bulletins.

Three series come out of this: Maharashtra, Madhya Pradesh and all-India.
MH + MP is the proxy for MOIL's operating region (~49% of national output);
all-India is kept for sanity-checking and dashboard context, not as a
forecast target.

Two tables in each bulletin carry the numbers:

  Table 3  mineral-wise, all-India     "Manganese Ore t 439949.424 34,64,042 ..."
  Table 4  mineral and state-wise      "Manganese Ore t" then India + state rows

Page numbers in the bulletins are *printed* page numbers, which sit ~13 pages
ahead of the PDF page index and drift between issues, so nothing here is
keyed to a page number. Instead each page is classified by its caption:

  "3. MINERAL PRODUCTION, <month>"   -> Table 3
  "4. MINERAL PRODUCTION, <month>"   -> Table 4
  "5. MINERAL PRODUCTION, <month>"   -> per-state sections, deliberately ignored

Table 5 matters because its per-state pages repeat the exact
"Manganese Ore t <numbers>" shape as Table 3; matching on that line alone
picks up Andhra Pradesh's figure and reports it as all-India.

Every quantity in these tables is printed with exactly three decimals, which
is what separates a data row from a heading.

Run: python -m src.data.preprocess.parse_msmp_manganese
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pdfplumber
from pypdf import PdfReader

from src.config.settings import settings

PDF_DIR: Path = settings.DATA_RAW / "moil" / "msmp_pdfs"
WIDE_PATH: Path = settings.DATA_PROCESSED / "msmp_mn_monthly_wide.parquet"
LONG_PATH: Path = settings.DATA_PROCESSED / "msmp_mn_monthly_long.parquet"
FAILURES_PATH: Path = settings.DATA_PROCESSED / "msmp_parse_failures.csv"

#: Embedded-font artefacts pdfplumber emits for Devanagari glyphs.
CID = re.compile(r"\(cid:\d+\)")
CAPTION = re.compile(r"\b([345])\.\s*MINERAL\s+PRODUCTION", re.I)
MANGANESE = re.compile(r"Manganese\s*Ore", re.I)

#: Quantities are 3-decimal from roughly 2021 ("106289.750") but bare integers
#: in the older bulletins ("180572"), so the decimal part has to be optional.
#: Requiring it silently failed every pre-decimal-era file.
NUM = r"(\d[\d,]*(?:\.\d+)?)"

#: "Maharashtra 106289.750 11,85,780" - name, quantity, then a value that may
#: be an Indian-grouped integer or "-" when unavailable.
DATA_ROW = re.compile(r"([A-Za-z][A-Za-z&.\s]*[A-Za-z])\s+" + NUM + r"\s+([\d,]+|-)")
#: Table 3's own line carries the unit before the numbers.
T3_ROW = re.compile(
    r"Manganese\s*Ore\s+([A-Za-z'\d.]+)\s+" + NUM + r"\s+([\d,]+|-)", re.I
)
#: The manganese block can run past the foot of a page, marked "Contd...".
CONTD = re.compile(r"contd", re.I)

#: Pre-2021 bulletins render Hindi as Roman transliteration rather than
#: Devanagari, so a row reads "Hkkjr India 180572 ..." and the raw capture is
#: "Hkkjr India". Each row is reduced to the canonical name it ends with.
GEOGRAPHIES: tuple[str, ...] = (
    "India",
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jammu And Kashmir",
    "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra",
    "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Orissa",
    "Offshore", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana",
    "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
)
#: Longest first so "Madhya Pradesh" wins over a bare "Pradesh" suffix.
_BY_LENGTH: tuple[str, ...] = tuple(sorted(GEOGRAPHIES, key=len, reverse=True))

#: August 2024 sets the state column in capitals and wraps two-word names, so
#: the figures sit on a "MADHYA 60,499.980 ..." line with a bare "PRADESH"
#: underneath. The first word alone therefore has to resolve.
FIRST_WORD: dict[str, str] = {
    "andhra": "Andhra Pradesh",
    "arunachal": "Arunachal Pradesh",
    "himachal": "Himachal Pradesh",
    "madhya": "Madhya Pradesh",
    "tamil": "Tamil Nadu",
    "uttar": "Uttar Pradesh",
    "west": "West Bengal",
    "jammu": "Jammu And Kashmir",
}
#: The orphaned tail of such a wrapped name, which carries no figures and must
#: not be read as the end of the block.
NAME_TAIL = re.compile(r"^(pradesh|bengal|nadu|kashmir|and\s+kashmir)$", re.I)


def canonical(name: str) -> str:
    """Reduce a raw row label to its canonical geography, if it is one."""
    squashed = " ".join(name.split())
    lowered = squashed.lower()
    for geography in _BY_LENGTH:
        if lowered.endswith(geography.lower()):
            return geography
    last = lowered.split()[-1] if lowered.split() else ""
    if last in FIRST_WORD:
        return FIRST_WORD[last]
    return squashed

TOLERANCE = 0.005  # 0.5% for both reconciliation checks
MOM_WARN = 0.60  # 60% month-over-month change is suspicious, not fatal
MAX_STATE_TONNES = 1_000_000
MAX_INDIA_TONNES = 2_000_000


def clean(text: str | None) -> str:
    return CID.sub("", text or "")


def to_number(token: str) -> float | None:
    token = token.strip().replace(",", "")
    if token in {"", "-"}:
        return None
    try:
        return float(token)
    except ValueError:
        return None


def classify_page(text: str) -> str | None:
    """Return '3', '4', '5' or None from the page caption."""
    match = CAPTION.search(text)
    return match.group(1) if match else None


def parse_table3(lines: list[str]) -> tuple[float, float] | None:
    """All-India quantity and value from the mineral-wise table."""
    for line in lines:
        match = T3_ROW.search(line)
        if match:
            qty = to_number(match.group(2))
            value = to_number(match.group(3))
            if qty is not None:
                return qty, value if value is not None else float("nan")
    return None


def geo_row(line: str) -> tuple[str, float, float] | None:
    """Parse a line as (geography, quantity, value), or None if it is not one.

    Requiring a recognised geography is what keeps the repeated page headers
    out: a continuation page reprints "January 2016 December 2015 ..." which
    matches the name-then-numbers shape but is not a data row.
    """
    match = DATA_ROW.search(line)
    if not match:
        return None
    name = canonical(match.group(1))
    if name not in GEOGRAPHIES:
        return None
    qty = to_number(match.group(2))
    if qty is None:
        return None
    value = to_number(match.group(3))
    return name, qty, value if value is not None else float("nan")


def _collect_rows(
    lines: list[str], start: int, seen: dict[str, tuple[float, float]] | None = None
) -> tuple[dict[str, tuple[float, float]], bool]:
    """Read data rows from `start`; also report whether the block continues.

    A mineral heading carries no figures, so the first line that is not a data
    row closes the block. Running off the end of the page, or hitting a
    "Contd..." marker, means it spills onto the next Table 4 page instead.
    """
    rows: dict[str, tuple[float, float]] = {}
    already = seen or {}
    for line in lines[start:]:
        if CONTD.search(line):
            return rows, True
        if NAME_TAIL.match(line.strip()):
            continue  # the wrapped remainder of the previous row's state name
        parsed = geo_row(line)
        if parsed is None:
            return rows, False
        name, qty, value = parsed
        # Every mineral block opens with its own India row, so seeing a
        # geography twice means this is the next mineral, not more manganese.
        # The check spans the whole block, not just this page: a page footer
        # ending in "Contd..." otherwise sends the reader onto the next page,
        # where the following mineral's India row silently replaces ours.
        if name in rows or name in already:
            return rows, False
        rows[name] = (qty, value)
    return rows, True  # ran to the foot of the page


def parse_table4(pages: list[list[str]]) -> dict[str, tuple[float, float]]:
    """Geography -> (quantity, value), across however many pages it spans.

    `pages` holds the lines of each Table 4 page in document order. January
    2016 splits manganese after Gujarat, so a single-page read would capture
    four of nine states and fail the state-sum reconciliation.
    """
    rows: dict[str, tuple[float, float]] = {}
    continuing = False

    for lines in pages:
        if not rows and not continuing:
            heading = next(
                (
                    i
                    for i, line in enumerate(lines)
                    if MANGANESE.search(line) and not DATA_ROW.search(line)
                ),
                None,
            )
            if heading is None:
                continue
            found, continuing = _collect_rows(lines, heading + 1, rows)
            rows.update(found)
            continue

        if continuing:
            # Resume at the first data row, stepping over the repeated page
            # header, caption and column titles.
            resume = next(
                (i for i, line in enumerate(lines) if geo_row(line)), None
            )
            if resume is None:
                break
            found, continuing = _collect_rows(lines, resume, rows)
            rows.update(found)
            if not continuing:
                break

    return rows


def month_from_name(path: Path) -> pd.Period:
    _, year, month = path.stem.split("_")
    return pd.Period(f"{year}-{month}", freq="M")


def parse_pdf(path: Path) -> dict[str, object]:
    """Extract one bulletin. `error` is set when it cannot be trusted."""
    out: dict[str, object] = {
        "report_month": month_from_name(path),
        "source_pdf": path.name,
        "t3_page": None,
        "t4_page": None,
        "unreadable_pages": 0,
        "error": None,
    }

    table3: tuple[float, float] | None = None
    table4: dict[str, tuple[float, float]] = {}
    table4_pages: list[list[str]] = []

    fallback: PdfReader | None = None

    with pdfplumber.open(path) as pdf:
        bad_pages = 0
        for number, page in enumerate(pdf.pages, start=1):
            try:
                text = clean(page.extract_text())
            except Exception:
                # Some bulletins carry a malformed font descriptor that makes
                # pdfminer throw ("'PSKeyword' object has no attribute
                # 'decode'"). April 2026 loses 40 of 67 pages that way,
                # including its Table 3. pypdf reads those pages fine, so fall
                # back to it rather than dropping the bulletin.
                bad_pages += 1
                if fallback is None:
                    try:
                        fallback = PdfReader(str(path))
                    except Exception:
                        continue
                try:
                    text = clean(fallback.pages[number - 1].extract_text())
                except Exception:
                    continue
            kind = classify_page(text)
            if kind not in {"3", "4"}:
                continue  # table 5's per-state pages mimic table 3's shape
            # Table 4 pages are kept whether or not they name manganese: the
            # block spills onto a continuation page that repeats only the
            # column headers, so filtering on the mineral name drops the
            # states that follow the break.
            if kind == "3" and not MANGANESE.search(text):
                continue
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            if kind == "3" and table3 is None:
                found = parse_table3(lines)
                if found:
                    table3, out["t3_page"] = found, number
            elif kind == "4":
                table4_pages.append(lines)
                if out["t4_page"] is None and any(
                    MANGANESE.search(line) for line in lines
                ):
                    out["t4_page"] = number

    if table4_pages:
        table4 = parse_table4(table4_pages)

    out["unreadable_pages"] = bad_pages
    if table3 is None:
        out["error"] = "table3_manganese_row_not_found"
        return out
    if not table4:
        out["error"] = "table4_manganese_block_not_found"
        return out

    india = table4.get("India")
    maharashtra = table4.get("Maharashtra")
    madhya = table4.get("Madhya Pradesh")
    if india is None:
        out["error"] = "table4_india_row_missing"
        return out
    if maharashtra is None or madhya is None:
        missing = [
            n for n, v in (("Maharashtra", maharashtra), ("Madhya Pradesh", madhya)) if v is None
        ]
        out["error"] = f"table4_state_row_missing:{'+'.join(missing)}"
        return out

    states = {n: v for n, v in table4.items() if n != "India"}
    state_sum = sum(qty for qty, _ in states.values())

    # (a) state rows must reconstruct the table's own all-India row
    if india[0] > 0 and abs(state_sum - india[0]) / india[0] > TOLERANCE:
        out["error"] = (
            f"state_sum_mismatch:sum={state_sum:.3f},india={india[0]:.3f},"
            f"diff={abs(state_sum - india[0]) / india[0] * 100:.2f}%"
        )
        return out

    # (b) the same all-India number is printed in both tables
    if india[0] > 0 and abs(table3[0] - india[0]) / india[0] > TOLERANCE:
        out["error"] = (
            f"table3_table4_mismatch:t3={table3[0]:.3f},t4={india[0]:.3f},"
            f"diff={abs(table3[0] - india[0]) / india[0] * 100:.2f}%"
        )
        return out

    # (d) magnitudes must be physically sensible
    for label, (qty, limit) in {
        "maharashtra": (maharashtra[0], MAX_STATE_TONNES),
        "madhya_pradesh": (madhya[0], MAX_STATE_TONNES),
        "all_india": (india[0], MAX_INDIA_TONNES),
    }.items():
        if not 0 < qty < limit:
            out["error"] = f"implausible_{label}:{qty:.3f}"
            return out

    out.update(
        {
            "mh_qty_tonnes": maharashtra[0],
            "mp_qty_tonnes": madhya[0],
            "mh_plus_mp_qty_tonnes": maharashtra[0] + madhya[0],
            "all_india_qty_tonnes": india[0],
            "mh_value_rs_thousand": maharashtra[1],
            "mp_value_rs_thousand": madhya[1],
            "all_india_value_rs_thousand": india[1],
            "n_states": len(states),
            "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    )
    return out


def build(limit: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    pdfs = sorted(PDF_DIR.glob("MSMP_*.pdf"))
    if limit:
        pdfs = pdfs[:limit]

    parsed: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    for position, path in enumerate(pdfs, start=1):
        try:
            record = parse_pdf(path)
        except Exception as exc:  # a corrupt PDF must not stop the batch
            failures.append(
                {
                    "source_pdf": path.name,
                    "report_month": str(month_from_name(path)),
                    "reason": f"exception:{type(exc).__name__}:{exc}",
                }
            )
            continue
        if record["error"]:
            failures.append(
                {
                    "source_pdf": path.name,
                    "report_month": str(record["report_month"]),
                    "reason": str(record["error"]),
                }
            )
        else:
            parsed.append(record)
        if position % 20 == 0:
            print(f"    {position}/{len(pdfs)}  clean={len(parsed)} failed={len(failures)}")

    wide = pd.DataFrame(parsed)
    fail_frame = pd.DataFrame(failures)

    if not wide.empty:
        wide = wide.sort_values("report_month").reset_index(drop=True)
        # (c) month-over-month sanity: warn, never drop
        for column in ("mh_qty_tonnes", "mp_qty_tonnes", "all_india_qty_tonnes"):
            change = wide[column].pct_change().abs()
            for row in wide[change > MOM_WARN].itertuples():
                print(
                    f"    WARN {row.report_month} {column} moved "
                    f"{change[row.Index] * 100:.0f}% vs previous month"
                )
        wide = wide.drop(columns=["error", "t3_page", "t4_page", "unreadable_pages"])

    return wide, fail_frame


def to_long(wide: pd.DataFrame) -> pd.DataFrame:
    if wide.empty:
        return pd.DataFrame(
            columns=["report_month", "geography", "qty_tonnes", "value_rs_thousand"]
        )
    mapping = {
        "MH": ("mh_qty_tonnes", "mh_value_rs_thousand"),
        "MP": ("mp_qty_tonnes", "mp_value_rs_thousand"),
        "MH+MP": ("mh_plus_mp_qty_tonnes", None),
        "all_india": ("all_india_qty_tonnes", "all_india_value_rs_thousand"),
    }
    frames = []
    for geography, (qty_col, value_col) in mapping.items():
        part = pd.DataFrame(
            {
                "report_month": wide["report_month"],
                "geography": geography,
                "qty_tonnes": wide[qty_col],
                "value_rs_thousand": (
                    wide[value_col] if value_col else pd.NA
                ),
            }
        )
        frames.append(part)
    return pd.concat(frames, ignore_index=True).sort_values(
        ["report_month", "geography"]
    ).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    wide, failures = build(limit=args.limit)
    settings.DATA_PROCESSED.mkdir(parents=True, exist_ok=True)

    if not wide.empty:
        wide.to_parquet(WIDE_PATH, index=False)
        to_long(wide).to_parquet(LONG_PATH, index=False)
    failures.to_csv(FAILURES_PATH, index=False)

    total = len(wide) + len(failures)
    print()
    print("=" * 70)
    print("MSMP MANGANESE PARSE SUMMARY")
    print("=" * 70)
    print(f"  bulletins    : {total}")
    print(f"  clean        : {len(wide)}")
    print(f"  failed       : {len(failures)}")
    if not wide.empty:
        print(f"  span         : {wide.report_month.min()} .. {wide.report_month.max()}")
        print(f"  wide  -> {WIDE_PATH}")
        print(f"  long  -> {LONG_PATH}")
    print(f"  failures -> {FAILURES_PATH}")


if __name__ == "__main__":
    main()
