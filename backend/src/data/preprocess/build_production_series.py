"""
Build MOIL production series from the cached BSE press releases.

Three figure types appear in the same releases:

  monthly      "MOIL has recorded production of 1.63 lakh tonnes" (November)
  FY-to-date   "During first eight months of FY25 ... 11.80 lakh tonnes"
  annual       "best ever production of 17.6 lakh tonnes in FY'24"

Only the first was used before, which threw away most of the signal. Two
consecutive FY-to-date figures differ by exactly the months between them, so
differencing recovers months that never got their own release - and the
annual figures anchor whole years back before monthly releases began.

Outputs a monthly series (direct + reconstructed) and a quarterly series,
each row carrying how it was derived so nothing is silently synthetic.

Run: python -m src.data.preprocess.build_production_series
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from src.config.settings import settings
from src.data.ingest.scrape_moil_bse import (
    MAX_MONTH_TONNES,
    MIN_MONTH_TONNES,
    MONTHS,
    PDF_CACHE,
    fiscal_year,
)
from src.db.session import get_engine

MONTHLY_PATH: Path = settings.DATA_PROCESSED / "moil_monthly_series.parquet"
QUARTERLY_PATH: Path = settings.DATA_PROCESSED / "moil_quarterly_series.parquet"
SUMMARY_PATH: Path = settings.DATA_PROCESSED / "moil_series_summary.json"

NUMBER = r"([\d,]+(?:\.\d+)?)"
#: MOIL writes FY'25 with a Unicode right single quote (U+2019), not an ASCII
#: apostrophe. Matching only "'" found zero cumulative figures in the real PDFs
#: despite matching a hand-typed test string.
QUOTE = r"[‘’ʼ'`´�?]?"

#: Any production figure: "Achieved production of 13.30 lakh MT of manganese ore"
FIGURE_RE = re.compile(
    r"production\s+of\s+" + NUMBER + r"\s*(lakh\s+)?(?:tonnes?|MT)\b", re.I
)
#: "first nine months of FY'25" - the release is then reporting a cumulative
#: FY-to-date total, not that month's output.
CUMULATIVE_MARKER = re.compile(
    r"first\s+(\w+)\s+months?\s+(?:ended\s+)?of\s+FY\s*" + QUOTE + r"\s*(\d{2,4})",
    re.I,
)
#: A quarter/half/nine-month results release, where a bare figure is cumulative.
PERIOD_MARKER = re.compile(
    r"(?:quarter|half\s*year|nine\s+months|six\s+months|third\s+quarter|"
    r"second\s+quarter|first\s+quarter|fourth\s+quarter)", re.I
)
#: "in FY'24" / "for FY 2023-24" - a whole-year total.
ANNUAL_MARKER = re.compile(
    r"(?:in|during|for|of)\s+FY\s*" + QUOTE + r"\s*(\d{2,4})(?:\s*-\s*\d{2,4})?", re.I
)
#: The month a monthly release is about.
MONTH_NAME = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\b",
    re.I,
)

WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}


def _tonnes(value: str, lakh: object) -> float:
    number = float(str(value).replace(",", ""))
    return number * 100_000 if lakh else number


def _months_count(token: str) -> int | None:
    token = str(token).strip().lower()
    if token.isdigit():
        count = int(token)
    else:
        count = WORD_NUMBERS.get(token, 0)
    return count if 1 <= count <= 12 else None


def _fy_start_year(token: str) -> int:
    """FY25 / FY2025 -> 2024 (the April in which that fiscal year began)."""
    digits = int(str(token))
    year = digits if digits > 100 else 2000 + digits
    return year - 1


def extract_observations() -> pd.DataFrame:
    """Every production figure in the cached releases, typed by kind.

    Typing is done per-figure by looking at what precedes it, because MOIL
    mixes kinds inside one release:

      monthly     "MOIL has recorded production of 1.63 lakh tonnes" (November)
      cumulative  "first nine months of FY'25 ... production of 13.30 lakh MT"
      annual      "production of 17.6 lakh tonnes in FY'24"

    The period marker can sit several sentences before the figure, separated by
    bullets full of full stops, so the search window deliberately spans
    sentence boundaries rather than stopping at the first period.
    """
    rows: list[dict[str, object]] = []

    for cached in sorted(PDF_CACHE.glob("*.txt")):
        body = cached.read_text(encoding="utf-8", errors="replace")
        if not body.strip():
            continue

        for figure in FIGURE_RE.finditer(body):
            tonnes = _tonnes(figure.group(1), figure.group(2))
            if tonnes <= 0:
                continue

            # Look back far enough to cross the bullet list that separates the
            # heading from the production line.
            window = body[max(0, figure.start() - 700) : figure.start()]
            after = body[figure.end() : figure.end() + 160]

            cumulative = None
            for marker in CUMULATIVE_MARKER.finditer(window):
                cumulative = marker  # nearest preceding marker wins
            annual = None
            for marker in ANNUAL_MARKER.finditer(window + after):
                annual = marker

            if cumulative is not None:
                count = _months_count(cumulative.group(1))
                # A cumulative total must be at least a month's worth per month.
                # A cumulative total has to be consistent with its own month
                # count, otherwise a stray monthly figure sitting under a
                # "first N months" heading gets logged as N months of output.
                plausible = (
                    count is not None
                    and MIN_MONTH_TONNES * count <= tonnes <= MAX_MONTH_TONNES * count
                )
                if plausible:
                    rows.append(
                        {
                            "kind": "cumulative",
                            "fy_start": _fy_start_year(cumulative.group(2)),
                            "n_months": count,
                            "tonnes": tonnes,
                            "source": cached.name,
                        }
                    )
                continue

            if 800_000 <= tonnes <= 2_500_000 and annual is not None:
                rows.append(
                    {
                        "kind": "annual",
                        "fy_start": _fy_start_year(annual.group(1)),
                        "n_months": 12,
                        "tonnes": tonnes,
                        "source": cached.name,
                    }
                )
                continue

            if MIN_MONTH_TONNES <= tonnes <= MAX_MONTH_TONNES:
                names = MONTH_NAME.findall(body[: figure.end() + 300])
                if names:
                    rows.append(
                        {
                            "kind": "monthly",
                            "month_name": names[-1].lower(),
                            "tonnes": tonnes,
                            "source": cached.name,
                            "fy_start": None,
                            "n_months": 1,
                        }
                    )

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.drop_duplicates(subset=["kind", "fy_start", "n_months", "tonnes"])


def load_direct_monthly() -> pd.DataFrame:
    sql = "SELECT period_month, production_tonnes FROM moil_monthly_production ORDER BY period_month"
    with get_engine().connect() as conn:
        rows = conn.execute(text(sql)).all()
    frame = pd.DataFrame(rows, columns=["period_month", "tonnes"])
    if frame.empty:
        return frame
    frame["period_month"] = pd.to_datetime(frame["period_month"])
    frame["tonnes"] = pd.to_numeric(frame["tonnes"], errors="coerce")
    frame["derivation"] = "direct_monthly_release"
    return frame.dropna()


def reconstruct_from_cumulative(observations: pd.DataFrame) -> pd.DataFrame:
    """Difference consecutive FY-to-date figures into single months.

    Two cumulative points in the same fiscal year that differ by exactly one
    month give that month's production outright. Wider gaps are left alone -
    spreading a three-month total evenly would be invention.
    """
    if observations.empty:
        return pd.DataFrame(columns=["period_month", "tonnes", "derivation"])

    cumulative = observations[observations.kind == "cumulative"]
    rows: list[dict[str, object]] = []
    for fy_start, group in cumulative.groupby("fy_start"):
        ordered = group.sort_values("n_months").drop_duplicates("n_months")
        previous_months, previous_tonnes = 0, 0.0
        for entry in ordered.itertuples():
            step = int(entry.n_months) - previous_months
            delta = float(entry.tonnes) - previous_tonnes
            if step == 1 and MIN_MONTH_TONNES <= delta <= MAX_MONTH_TONNES:
                month_index = (3 + int(entry.n_months) - 1) % 12 + 1
                year = int(fy_start) + (0 if month_index >= 4 else 1)
                rows.append(
                    {
                        "period_month": pd.Timestamp(year, month_index, 1),
                        "tonnes": delta,
                        "derivation": "cumulative_difference",
                    }
                )
            previous_months, previous_tonnes = int(entry.n_months), float(entry.tonnes)
    return pd.DataFrame(rows)


def build_monthly() -> pd.DataFrame:
    observations = extract_observations()
    direct = load_direct_monthly()
    derived = reconstruct_from_cumulative(observations)

    frame = pd.concat([direct, derived], ignore_index=True) if len(derived) else direct
    if frame.empty:
        raise RuntimeError("no monthly production could be assembled")

    # A direct release beats a differenced figure for the same month.
    priority = {"direct_monthly_release": 0, "cumulative_difference": 1}
    frame["rank"] = frame.derivation.map(priority).fillna(9)
    frame = (
        frame.sort_values(["period_month", "rank"])
        .drop_duplicates("period_month", keep="first")
        .drop(columns="rank")
        .reset_index(drop=True)
    )
    frame["fiscal_year"] = frame.period_month.map(lambda d: fiscal_year(d.date())[0])
    frame["fiscal_quarter"] = frame.period_month.map(lambda d: fiscal_year(d.date())[1])
    return frame


def build_quarterly(monthly: pd.DataFrame, observations: pd.DataFrame) -> pd.DataFrame:
    """Quarterly totals, only where all three months of a quarter are known.

    A partial quarter is reported as incomplete rather than scaled up, so a
    quarter built from two months never masquerades as a full one.
    """
    grouped = monthly.groupby(["fiscal_year", "fiscal_quarter"])
    rows: list[dict[str, object]] = []
    for (fy, quarter), group in grouped:
        rows.append(
            {
                "fiscal_year": fy,
                "fiscal_quarter": int(quarter),
                "period_quarter": group.period_month.min(),
                "tonnes": float(group.tonnes.sum()),
                "months_present": int(len(group)),
                "complete": bool(len(group) == 3),
                "derivation": "sum_of_months",
            }
        )
    frame = pd.DataFrame(rows).sort_values("period_quarter").reset_index(drop=True)
    return frame


def main() -> None:
    observations = extract_observations()
    monthly = build_monthly()
    quarterly = build_quarterly(monthly, observations)

    MONTHLY_PATH.parent.mkdir(parents=True, exist_ok=True)
    monthly.to_parquet(MONTHLY_PATH, index=False)
    quarterly.to_parquet(QUARTERLY_PATH, index=False)

    complete = quarterly[quarterly.complete]
    span = pd.period_range(monthly.period_month.min(), monthly.period_month.max(), freq="M")
    have = {pd.Period(d, freq="M") for d in monthly.period_month}
    gaps = [str(p) for p in span if p not in have]

    print("=" * 70)
    print("MOIL PRODUCTION SERIES")
    print("=" * 70)
    print(f"  cached releases parsed : {len(list(PDF_CACHE.glob('*.txt')))}")
    if not observations.empty:
        print("  figures extracted      :")
        for kind, group in observations.groupby("kind"):
            print(f"    {str(kind):<12} {len(group)}")
    print("")
    print(f"  monthly points         : {len(monthly)}")
    for derivation, group in monthly.groupby("derivation"):
        print(f"    {str(derivation):<26} {len(group)}")
    print(f"  span                   : {monthly.period_month.min().date()} .. {monthly.period_month.max().date()}")
    print(f"  gaps remaining         : {len(gaps)} of {len(span)} months")
    print(f"  tonnes range           : {monthly.tonnes.min():,.0f} .. {monthly.tonnes.max():,.0f}")
    print("")
    print(f"  quarters (any months)  : {len(quarterly)}")
    print(f"  quarters complete (3/3): {len(complete)}")
    if len(complete):
        print(f"  complete-quarter range : {complete.tonnes.min():,.0f} .. {complete.tonnes.max():,.0f} t")

    summary = {
        "monthly_points": int(len(monthly)),
        "monthly_by_derivation": monthly.derivation.value_counts().to_dict(),
        "monthly_span": [str(monthly.period_month.min().date()), str(monthly.period_month.max().date())],
        "monthly_gaps": len(gaps),
        "quarters_total": int(len(quarterly)),
        "quarters_complete": int(len(complete)),
        "observations_by_kind": (
            observations.kind.value_counts().to_dict() if not observations.empty else {}
        ),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"\n  monthly  -> {MONTHLY_PATH}")
    print(f"  quarterly-> {QUARTERLY_PATH}")


if __name__ == "__main__":
    main()
