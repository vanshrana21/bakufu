"""
Recover manganese figures from the five image-only MSMP bulletins.

Five of the 125 bulletins carry no text layer at all - every page returns zero
characters from both pdfplumber and pypdf - so the normal parser cannot see
them. They are not degraded scans: they are digitally produced PDFs whose text
was rasterised, with uniform typography and no skew, which is close to the
best case for Tesseract.

The pages are rendered with pypdfium2 (already present via pdfplumber, so no
poppler dependency), OCR'd to plain lines, and then handed to the *same*
`geo_row` / `DATA_ROW` helpers the text-based parser uses. Reusing that path
means the state-sum and table-3/table-4 reconciliation checks apply here
unchanged, rather than a second extraction route with its own blind spots.

Every figure is additionally asserted against values read by eye from the
rendered pages before any OCR was run. OCR failures are usually a wildly wrong
digit rather than a subtle drift, and an exact match against known-good values
catches that far more reliably than any tolerance band.

Run: python -m src.data.preprocess.ocr_msmp_scanned
"""

from __future__ import annotations

import argparse
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pypdfium2 as pdfium

from src.config.settings import settings
from src.data.preprocess.parse_msmp_manganese import (
    CONTD,
    DATA_ROW,
    MANGANESE,
    NAME_TAIL,
    T3_ROW,
    geo_row,
    to_number,
)

PDF_DIR: Path = settings.DATA_RAW / "moil" / "msmp_pdfs"
OCR_PATH: Path = settings.DATA_PROCESSED / "msmp_mn_ocr_recovered.parquet"
OCR_FAILURES: Path = settings.DATA_PROCESSED / "msmp_ocr_failures.csv"

#: Tesseract is installed per-user here and is not on PATH, so it is addressed
#: directly rather than depending on the shell environment.
TESSERACT_CANDIDATES = (
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Tesseract-OCR" / "tesseract.exe",
    Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
    Path("C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"),
)

#: Where each bulletin's tables live, established by rendering and reading the
#: pages by hand. `rotation` is applied at render time: July 2020's page is
#: printed sideways, and rotating deterministically is faster and less fragile
#: than asking Tesseract to detect orientation.
LAYOUT: dict[str, dict[str, object]] = {
    "MSMP_2020_07.pdf": {"t3": [19], "t4": [25, 26], "rotation": 90, "decimals": False},
    "MSMP_2024_09.pdf": {"decimals": True, "t3": [20], "t4": [27, 28], "rotation": 0},
    "MSMP_2025_02.pdf": {"decimals": True, "t3": [20], "t4": [27, 28], "rotation": 0},
    "MSMP_2025_05.pdf": {"decimals": True, "t3": [20], "t4": [28, 29], "rotation": 0},
    "MSMP_2025_10.pdf": {"decimals": True, "t3": [20], "t4": [28, 29], "rotation": 0},
}

#: Read by eye from the rendered pages before OCR was written. A month whose
#: OCR output does not match these exactly is rejected rather than published.
GROUND_TRUTH: dict[str, dict[str, float]] = {
    "MSMP_2020_07.pdf": {"t3": 133683.0, "mh": 36460.0, "mp": 53024.0},
    "MSMP_2024_09.pdf": {"t3": 246777.947, "mh": 87276.880, "mp": 79115.715},
    "MSMP_2025_02.pdf": {"t3": 387867.240, "mh": 117698.590, "mp": 87644.658},
    "MSMP_2025_05.pdf": {"t3": 356683.295, "mh": 103067.210, "mp": 100468.110},
    "MSMP_2025_10.pdf": {"t3": 278101.749, "mh": 102793.790, "mp": 83393.630},
}

RENDER_SCALE = 3.0  # ~216 dpi; enough for 8pt table digits
TESS_CONFIG = "--psm 6"  # one uniform block of text, preserving row order
TOLERANCE = 0.005


def find_tesseract() -> Path:
    for candidate in TESSERACT_CANDIDATES:
        if candidate.is_file():
            return candidate
    raise RuntimeError(
        "Tesseract not found. Install it and/or add its path to "
        "TESSERACT_CANDIDATES in this module."
    )


def ocr_page(pdf: pdfium.PdfDocument, page_number: int, rotation: int) -> list[str]:
    """Render one page and return its OCR'd lines."""
    import pytesseract

    image = pdf[page_number - 1].render(scale=RENDER_SCALE, rotation=rotation).to_pil()
    text = pytesseract.image_to_string(image, lang="eng", config=TESS_CONFIG)
    return [line.strip() for line in text.split("\n") if line.strip()]


def repair_digits(line: str) -> str:
    """Undo the substitutions Tesseract makes inside numbers.

    Only applied between digits, so state names are untouched: "O" in "Odisha"
    survives, while the "O" in "1O6289.750" becomes a zero.
    """
    swaps = {"O": "0", "o": "0", "l": "1", "I": "1", "|": "1", "S": "5", "B": "8"}
    out = list(line)
    for index in range(1, len(out) - 1):
        if out[index] in swaps and out[index - 1].isdigit() and out[index + 1].isdigit():
            out[index] = swaps[out[index]]
    text = "".join(out)
    # Tesseract sometimes reads the decimal point as a comma or space.
    text = re.sub(r"(\d),(\d{3})\b", r"\1\2", text)
    return text


def restore_decimals(line: str) -> str:
    """Put back a decimal point Tesseract dropped from a quantity.

    February 2025 read "87644.658" as "87644658", which sailed through the
    row regex as a plausible number and blew the state sum up to 87.9 million.
    Bulletins from 2021 onward always print quantities to exactly three
    decimals, so a bare integer in the quantity column is a dropped point.
    Only applied to the decimal-era files; 2020 really does use integers.

    Tesseract loses the point two different ways, and they need opposite
    fixes: February 2025 dropped it outright ("87644.658" -> "87644658"),
    while September 2024 read it as a space ("44944.302" -> "44944 302").
    Only the first quantity on the row is touched, because that is the only
    column the parser reads; later columns are left exactly as OCR'd.
    """
    match = DATA_ROW.search(line)
    if not match:
        return line

    head, tail = line[: match.end(1)], line[match.end(1) :]
    tokens = tail.split()
    if not tokens:
        return line

    first = tokens[0].replace(",", "")
    if not first.isdigit():  # already carries a decimal point
        return line

    if len(tokens) > 1 and re.fullmatch(r"\d{3}", tokens[1]):
        merged = [f"{first}.{tokens[1]}"] + tokens[2:]  # the point became a space
    elif len(first) >= 4:
        merged = [f"{first[:-3]}.{first[-3:]}"] + tokens[1:]  # the point vanished
    else:
        return line
    return f"{head} " + " ".join(merged)


def parse_t3(lines: list[str], decimals: bool = False) -> tuple[float, float] | None:
    for raw in lines:
        line = repair_digits(raw)
        if decimals:
            line = restore_decimals(line)
        match = T3_ROW.search(line)
        if match:
            qty = to_number(match.group(2))
            value = to_number(match.group(3))
            if qty is not None:
                return qty, value if value is not None else float("nan")
    return None


def parse_t4(pages: list[list[str]], decimals: bool = False) -> dict[str, tuple[float, float]]:
    """Manganese block across however many pages it spans.

    Mirrors the text parser: the block opens at a "Manganese Ore" heading with
    no figures on it, and each geography may appear only once - a repeat means
    the next mineral has started.
    """
    rows: dict[str, tuple[float, float]] = {}
    started = False

    for lines in pages:
        repaired = [repair_digits(line) for line in lines]
        if decimals:
            repaired = [restore_decimals(line) for line in repaired]
        start = 0
        if not started:
            heading = next(
                (
                    i
                    for i, line in enumerate(repaired)
                    if MANGANESE.search(line) and not geo_row(line)
                ),
                None,
            )
            if heading is None:
                continue
            started, start = True, heading + 1
        else:
            resume = next((i for i, line in enumerate(repaired) if geo_row(line)), None)
            if resume is None:
                break
            start = resume

        closed = False
        for line in repaired[start:]:
            if CONTD.search(line):
                break
            if NAME_TAIL.match(line):
                continue
            parsed = geo_row(line)
            if parsed is None:
                closed = True
                break
            name, qty, value = parsed
            if name in rows:
                closed = True
                break
            rows[name] = (qty, value)
        if closed:
            break

    return rows


def recover(name: str) -> dict[str, object]:
    """OCR one bulletin and validate it against the hand-read figures."""
    import pytesseract

    pytesseract.pytesseract.tesseract_cmd = str(find_tesseract())

    layout = LAYOUT[name]
    year, month = name.removesuffix(".pdf").split("_")[1:]
    record: dict[str, object] = {
        "report_month": pd.Period(f"{year}-{month}", freq="M"),
        "source_pdf": name,
        "error": None,
    }

    pdf = pdfium.PdfDocument(PDF_DIR / name)
    try:
        rotation = int(layout["rotation"])
        t3_lines: list[str] = []
        for page in layout["t3"]:  # type: ignore[union-attr]
            t3_lines += ocr_page(pdf, int(page), rotation)
        t4_pages = [ocr_page(pdf, int(page), rotation) for page in layout["t4"]]  # type: ignore[union-attr]
    finally:
        pdf.close()

    decimals = bool(layout.get("decimals", False))
    table3 = parse_t3(t3_lines, decimals)
    if table3 is None:
        record["error"] = "ocr_table3_not_found"
        return record

    table4 = parse_t4(t4_pages, decimals)
    india = table4.get("India")
    maharashtra = table4.get("Maharashtra")
    madhya = table4.get("Madhya Pradesh")
    if india is None or maharashtra is None or madhya is None:
        missing = [
            label
            for label, value in (
                ("India", india), ("Maharashtra", maharashtra), ("Madhya Pradesh", madhya)
            )
            if value is None
        ]
        record["error"] = f"ocr_rows_missing:{'+'.join(missing)}"
        return record

    states = {n: v for n, v in table4.items() if n != "India"}
    state_sum = sum(qty for qty, _ in states.values())

    if india[0] > 0 and abs(state_sum - india[0]) / india[0] > TOLERANCE:
        record["error"] = (
            f"state_sum_mismatch:sum={state_sum:.3f},india={india[0]:.3f}"
        )
        return record
    if india[0] > 0 and abs(table3[0] - india[0]) / india[0] > TOLERANCE:
        record["error"] = (
            f"table3_table4_mismatch:t3={table3[0]:.3f},t4={india[0]:.3f}"
        )
        return record

    # Exact agreement with the values read by eye, or the month is rejected.
    truth = GROUND_TRUTH[name]
    observed = {"t3": table3[0], "mh": maharashtra[0], "mp": madhya[0]}
    wrong = {
        key: (observed[key], expected)
        for key, expected in truth.items()
        if abs(observed[key] - expected) > 1e-3
    }
    if wrong:
        detail = ",".join(f"{k}:got={g:.3f},want={w:.3f}" for k, (g, w) in wrong.items())
        record["error"] = f"ocr_ground_truth_mismatch:{detail}"
        return record

    record.update(
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
            "extraction_method": "tesseract_ocr",
        }
    )
    return record


def neighbourhood_check(combined: pd.DataFrame) -> pd.DataFrame:
    """Flag OCR months that sit far outside their local variation.

    A backstop for months added later that have no hand-read ground truth.
    Compares MH+MP against the mean of the neighbouring months, scaled by the
    rolling 6-month standard deviation.
    """
    frame = combined.sort_values("report_month").reset_index(drop=True)
    series = frame["mh_plus_mp_qty_tonnes"]
    neighbour_mean = (series.shift(1) + series.shift(-1)) / 2
    rolling_sd = series.rolling(6, min_periods=3, center=True).std()
    deviation = (series - neighbour_mean).abs()
    frame["neighbourhood_flag"] = (deviation > 3 * rolling_sd) & rolling_sd.notna()
    return frame


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()

    recovered: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []

    print("=" * 70)
    print("OCR RECOVERY OF IMAGE-ONLY MSMP BULLETINS")
    print("=" * 70)
    for name in sorted(LAYOUT):
        try:
            record = recover(name)
        except Exception as exc:
            failures.append(
                {"source_pdf": name, "report_month": name[5:12], "reason": f"exception:{exc}"}
            )
            print(f"  {name}: EXCEPTION {exc}")
            continue

        if record["error"]:
            failures.append(
                {
                    "source_pdf": name,
                    "report_month": str(record["report_month"]),
                    "reason": str(record["error"]),
                }
            )
            print(f"  {name}: FAILED  {record['error']}")
        else:
            recovered.append(record)
            print(
                f"  {name}: OK  MH={record['mh_qty_tonnes']:>11.3f} "
                f"MP={record['mp_qty_tonnes']:>11.3f} "
                f"India={record['all_india_qty_tonnes']:>11.3f}"
            )

    frame = pd.DataFrame(recovered)
    if not frame.empty:
        frame = frame.drop(columns=["error"]).sort_values("report_month")
        frame.to_parquet(OCR_PATH, index=False)
    pd.DataFrame(failures).to_csv(OCR_FAILURES, index=False)

    print()
    print(f"  recovered : {len(recovered)}/{len(LAYOUT)}")
    print(f"  failed    : {len(failures)}")
    if not frame.empty:
        print(f"  parquet -> {OCR_PATH}")
    print(f"  failures -> {OCR_FAILURES}")


if __name__ == "__main__":
    main()
