"""Tests for the MSMP bulletin downloader and manganese parser.

The parser tests run against real bulletins rather than fixtures, because
every bug found while building it came from layout drift that a hand-made
fixture would not have reproduced: printed page numbers that differ from PDF
indices, integer quantities before 2021, Roman-transliterated Hindi, blocks
split across pages, and a page footer that sends the reader into the next
mineral's rows.

Tests needing a PDF skip when it is absent, so the suite still runs on a
checkout without the ~547 MB of downloaded bulletins.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.data.ingest import download_msmp_archive as dl
from src.data.preprocess import parse_msmp_manganese as parser

PDF_DIR = parser.PDF_DIR

#: Verified by hand against the May 2026 bulletin.
MAY_2026 = {"mh": 106289.750, "mp": 108334.530, "india": 439949.424}
#: Same, for the fallback month in the validation batch.
APRIL_2026_INDIA = 365024.976


def _pdf(name: str) -> Path:
    path = PDF_DIR / name
    if not path.exists():
        pytest.skip(f"{name} not downloaded; run download_msmp_archive first")
    return path


# --- downloader ---------------------------------------------------------


def test_downloader_is_idempotent(tmp_path, monkeypatch) -> None:
    """A second run re-uses files on disk and makes no HTTP calls."""
    archive = tmp_path / "archive.csv"
    archive.write_text(
        "report_month,release_date,pdf_url,file_size_if_shown,notes\n"
        "Jan 2016,2016-08-10,https://example.invalid/a.pdf,x,\n"
        "Feb 2016,2016-08-11,https://example.invalid/b.pdf,x,\n",
        encoding="utf-8",
    )
    pdf_dir = tmp_path / "pdfs"
    monkeypatch.setattr(dl, "ARCHIVE_CSV", archive)
    monkeypatch.setattr(dl, "PDF_DIR", pdf_dir)
    monkeypatch.setattr(dl, "DOWNLOAD_LOG", tmp_path / "download_log.csv")
    monkeypatch.setattr(dl, "SKIPPED_LOG", tmp_path / "skipped.csv")
    monkeypatch.setattr(dl.time, "sleep", lambda _seconds: None)

    body = b"%PDF-1.4\n" + b"0" * (dl.MIN_PDF_BYTES + 1)
    calls: list[str] = []

    def fake_fetch(_session, url, delay):
        calls.append(url)
        return body, "ok", delay

    monkeypatch.setattr(dl, "fetch", fake_fetch)

    first = dl.download_all()
    assert len(calls) == 2
    assert (first.status == "ok").sum() == 2

    second = dl.download_all()
    assert len(calls) == 2, "second run must not issue any HTTP request"
    assert (second.status == "skipped_existing").all()
    # The cached bytes are still reported, so the log stays complete.
    assert (second.bytes > 0).all()


def test_downloader_drops_only_the_superseded_advance_release() -> None:
    """Final releases mention an advance release; only one row is superseded.

    Matching "advance release" as well as "superseded" silently dropped four
    real months (Mar 2017, 2020, 2021, 2022).
    """
    if not dl.ARCHIVE_CSV.exists():
        pytest.skip("archive CSV not present")
    keep, skipped = dl.load_archive()

    assert len(keep) == keep.month.nunique(), "one row per month after dedup"
    reasons = skipped.reason.value_counts().to_dict()
    assert reasons.get("superseded_advance_release") == 1
    march_months = sorted({m.year for m in keep.month if m.month == 3})
    assert march_months == list(range(2016, 2027)), "every March must survive"


def test_downloader_rejects_html_error_pages(monkeypatch) -> None:
    """IBM serves an HTML error page with a 200; it must not be saved."""

    class FakeResponse:
        status_code = 200
        content = b"<!DOCTYPE html><html>Not found</html>"

    monkeypatch.setattr(dl.time, "sleep", lambda _seconds: None)
    session = type("S", (), {"get": lambda *a, **k: FakeResponse()})()

    body, status, _ = dl.fetch(session, "https://example.invalid/x.pdf", 0.0)
    assert body is None
    assert status == "failed_not_pdf"


# --- parser -------------------------------------------------------------


def test_parser_recovers_may_2026() -> None:
    """Ground truth from the earlier manual validation."""
    record = parser.parse_pdf(_pdf("MSMP_2026_05.pdf"))

    assert record["error"] is None
    assert record["mh_qty_tonnes"] == pytest.approx(MAY_2026["mh"], abs=1e-3)
    assert record["mp_qty_tonnes"] == pytest.approx(MAY_2026["mp"], abs=1e-3)
    assert record["all_india_qty_tonnes"] == pytest.approx(MAY_2026["india"], abs=1e-3)
    assert record["mh_plus_mp_qty_tonnes"] == pytest.approx(
        MAY_2026["mh"] + MAY_2026["mp"], abs=1e-3
    )


def test_parser_recovers_april_2026() -> None:
    """April is the fallback ground truth, and needs the pypdf path.

    Its Table 3 page is one of 40 that pdfminer cannot read because of a
    malformed font descriptor.
    """
    record = parser.parse_pdf(_pdf("MSMP_2026_04.pdf"))

    assert record["error"] is None
    assert record["all_india_qty_tonnes"] == pytest.approx(APRIL_2026_INDIA, abs=1e-3)
    assert record["unreadable_pages"] > 0, "expected the pdfminer font failure"


def test_parser_handles_page_drift() -> None:
    """March 2026's tables sit on different pages than May 2026's.

    The bulletins' own page numbers are printed page numbers, roughly 13
    ahead of the PDF index and drifting between issues, so the parser locates
    tables by caption instead. This asserts that behaviour rather than a
    literal index.
    """
    march = parser.parse_pdf(_pdf("MSMP_2026_03.pdf"))
    may = parser.parse_pdf(_pdf("MSMP_2026_05.pdf"))

    assert march["error"] is None
    assert march["t3_page"] != may["t3_page"], "the drift case must actually drift"
    assert march["t4_page"] != may["t4_page"]
    # Found well past the printed page 7/9, proving no page is hardcoded.
    assert march["t3_page"] > 12 and march["t4_page"] > march["t3_page"]
    assert march["all_india_qty_tonnes"] > 0


def test_parser_reads_pre_decimal_era() -> None:
    """2016 prints integer quantities and transliterates Hindi in Roman.

    "Hkkjr India 180572 ..." must resolve to India, and the block continues
    onto a second page after a "Contd..." marker.
    """
    record = parser.parse_pdf(_pdf("MSMP_2016_01.pdf"))

    assert record["error"] is None
    assert record["all_india_qty_tonnes"] == pytest.approx(180572.0, abs=1e-3)
    assert record["n_states"] >= 9, "states continue past the page break"


def test_sanity_check_rejects_bad_extraction(tmp_path, monkeypatch) -> None:
    """A state sum that disagrees with all-India lands in the failure log."""
    good = {
        "report_month": pd.Period("2024-02", freq="M"),
        "source_pdf": "GOOD.pdf",
        "error": None,
        "t3_page": 20,
        "t4_page": 28,
        "unreadable_pages": 0,
        "mh_qty_tonnes": 100.0,
        "mp_qty_tonnes": 100.0,
        "mh_plus_mp_qty_tonnes": 200.0,
        "all_india_qty_tonnes": 400.0,
        "mh_value_rs_thousand": 1.0,
        "mp_value_rs_thousand": 1.0,
        "all_india_value_rs_thousand": 1.0,
        "n_states": 7,
        "extracted_at": "2026-09-09T00:00:00+00:00",
    }
    bad = {
        "report_month": pd.Period("2024-01", freq="M"),
        "source_pdf": "BAD.pdf",
        "error": "state_sum_mismatch:sum=331297.000,india=60695.000,diff=445.84%",
        "t3_page": None,
        "t4_page": None,
        "unreadable_pages": 0,
    }
    by_name = {"BAD.pdf": bad, "GOOD.pdf": good}

    monkeypatch.setattr(parser, "PDF_DIR", tmp_path)
    for name in by_name:
        (tmp_path / f"MSMP_2024_{'01' if name == 'BAD.pdf' else '02'}.pdf").write_bytes(b"%PDF")
    monkeypatch.setattr(
        parser,
        "parse_pdf",
        lambda path: by_name["BAD.pdf" if path.name.endswith("01.pdf") else "GOOD.pdf"],
    )

    wide, failures = parser.build()

    assert len(wide) == 1 and wide.iloc[0].source_pdf == "GOOD.pdf"
    assert len(failures) == 1
    # The failure log names the file on disk, so a bad month can be traced
    # back to its PDF even when the record itself could not be built.
    assert failures.iloc[0].source_pdf == "MSMP_2024_01.pdf"
    assert failures.iloc[0].report_month == "2024-01"
    assert failures.iloc[0].reason.startswith("state_sum_mismatch")
    assert pd.Period("2024-01", freq="M") not in set(
        wide.report_month
    ), "failed months must not reach the clean output"


def test_state_sum_tolerance_is_enforced() -> None:
    """The 0.5% reconciliation is what caught the 2023-24 corruption."""
    assert parser.TOLERANCE == 0.005
    # 285-477% off in the real failures, so nowhere near the boundary.
    assert abs(256272.0 - 48716.0) / 48716.0 > parser.TOLERANCE


def test_canonical_resolves_geography_spellings() -> None:
    """Row labels arrive with transliterated or wrapped prefixes."""
    assert parser.canonical("Hkkjr India") == "India"
    assert parser.canonical("e/; izns'k Madhya Pradesh") == "Madhya Pradesh"
    assert parser.canonical('egkjk"Vª Maharashtra') == "Maharashtra"
    # August 2024 wraps capitalised names across lines.
    assert parser.canonical("MADHYA") == "Madhya Pradesh"
    assert parser.canonical("ANDHRA") == "Andhra Pradesh"
    assert parser.canonical("Some Mineral") == "Some Mineral"


def test_table5_pages_are_not_mistaken_for_table3() -> None:
    """Per-state pages repeat Table 3's shape with one state's figure.

    Andhra Pradesh's row would otherwise be reported as all-India.
    """
    assert parser.classify_page("5. MINERAL PRODUCTION, May 2026") == "5"
    assert parser.classify_page("3. MINERAL PRODUCTION, May 2026") == "3"
    assert parser.classify_page("4. MINERAL PRODUCTION, May 2026") == "4"


def test_outputs_match_the_documented_schema() -> None:
    """The wide and long parquet files carry the agreed columns."""
    if not parser.WIDE_PATH.exists():
        pytest.skip("parquet not built; run parse_msmp_manganese first")

    wide = pd.read_parquet(parser.WIDE_PATH)
    expected = {
        "report_month", "mh_qty_tonnes", "mp_qty_tonnes", "mh_plus_mp_qty_tonnes",
        "all_india_qty_tonnes", "mh_value_rs_thousand", "mp_value_rs_thousand",
        "all_india_value_rs_thousand", "source_pdf", "extracted_at",
    }
    assert expected <= set(wide.columns)
    assert (wide.mh_plus_mp_qty_tonnes - (wide.mh_qty_tonnes + wide.mp_qty_tonnes)).abs().max() < 1e-6
    assert (wide.all_india_qty_tonnes > 0).all()
    assert wide.report_month.is_unique

    long = pd.read_parquet(parser.LONG_PATH)
    assert set(long.geography.unique()) == {"MH", "MP", "MH+MP", "all_india"}
    assert len(long) == 4 * len(wide)


# --- OCR recovery ---------------------------------------------------------


def test_restore_decimals_handles_both_loss_modes() -> None:
    """Tesseract loses the decimal point two ways, needing opposite fixes."""
    from src.data.preprocess import ocr_msmp_scanned as ocr

    # February 2025: the point vanished outright.
    dropped = ocr.restore_decimals("MADHYA PRADESH 87644658 659847 92809378")
    assert "87644.658" in dropped
    # September 2024: the point was read as a space.
    spaced = ocr.restore_decimals("Odisha 44944 302 260160 32907.655")
    assert "44944.302" in spaced
    # A row that already has its point is left alone.
    intact = "Maharashtra 117698.590 1251895"
    assert ocr.restore_decimals(intact) == intact


def test_repair_digits_only_touches_numbers() -> None:
    """Letter/digit swaps must not corrupt state names."""
    from src.data.preprocess import ocr_msmp_scanned as ocr

    assert ocr.repair_digits("Odisha 1O6289.750 123") == "Odisha 106289.750 123"
    assert "Odisha" in ocr.repair_digits("Odisha 100.000 1")


def test_ocr_ground_truth_covers_every_scanned_file() -> None:
    """Each OCR'd month must have hand-read values to be checked against."""
    from src.data.preprocess import ocr_msmp_scanned as ocr

    assert set(ocr.LAYOUT) == set(ocr.GROUND_TRUTH)
    for name, truth in ocr.GROUND_TRUTH.items():
        assert {"t3", "mh", "mp"} <= set(truth), name


def test_ocr_recovered_months_match_ground_truth() -> None:
    """The published OCR figures equal the values read from the page."""
    from src.data.preprocess import ocr_msmp_scanned as ocr

    if not ocr.OCR_PATH.exists():
        pytest.skip("OCR output not built; run ocr_msmp_scanned first")

    frame = pd.read_parquet(ocr.OCR_PATH).set_index("source_pdf")
    for name, truth in ocr.GROUND_TRUTH.items():
        if name not in frame.index:
            continue
        row = frame.loc[name]
        assert row.mh_qty_tonnes == pytest.approx(truth["mh"], abs=1e-3), name
        assert row.mp_qty_tonnes == pytest.approx(truth["mp"], abs=1e-3), name
        assert row.all_india_qty_tonnes == pytest.approx(truth["t3"], abs=1e-3), name


def test_series_is_gap_free_over_the_backtest_window() -> None:
    """The last 24 months must be complete for a defensible backtest."""
    if not parser.WIDE_PATH.exists():
        pytest.skip("parquet not built")

    wide = pd.read_parquet(parser.WIDE_PATH)
    recent = pd.period_range("2024-06", "2026-05", freq="M")
    missing = [str(p) for p in recent if p not in set(wide.report_month)]
    assert not missing, f"gaps in the backtest window: {missing}"
