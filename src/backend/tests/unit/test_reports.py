"""Reports domain: formula-injection safety, filenames, period cap, PDF output."""

from datetime import date, datetime

import pytest

from app.contexts.reports.domain.csv_export import neutralize, render_csv
from app.contexts.reports.domain.summary import build_report, safe_filename
from app.contexts.reports.infrastructure.pdf import render_pdf
from app.shared.domain.date_range import DateRange
from app.shared.domain.errors import DomainError
from tests.factories import A, D, tx

PERIOD = DateRange.inclusive(date(2026, 11, 1), date(2026, 11, 20))
NOW = datetime(2026, 11, 20, 18, 30)


@pytest.mark.parametrize(
    "raw,safe",
    [
        ('=HYPERLINK("http://x")', '\'=HYPERLINK("http://x")'),
        ("+1+1", "'+1+1"),
        ("@SUM(A1)", "'@SUM(A1)"),
        ("-2+3", "'-2+3"),
        ("\tcmd", "'\tcmd"),
        ("Épicerie", "Épicerie"),
        ("-50.90", "-50.90"),
        ("1234", "1234"),
    ],
)
def test_formula_injection_is_neutralised_but_numbers_stay_numeric(raw, safe):
    assert neutralize(raw) == safe


def test_safe_filename_strips_anything_unexpected():
    name = safe_filename('M1/../"x";rm', PERIOD, "pdf")
    assert name == "ceo-pay_collections_M1-..-x-rm_2026-11-01_2026-11-20.pdf"
    assert "/" not in name and '"' not in name


def test_report_aggregates_and_period_cap():
    rows = [tx("a", A, "1000.00"), tx("b", A, "500.50"), tx("c", D, "200.00")]
    r = build_report("M1", "=Evil Shop", PERIOD, rows, [], NOW)
    assert r.kpis.gross_collected.centimes == 150050 and r.collected_change.kind.value == "new_activity"
    csv_text = render_csv(r).decode("utf-8")
    assert "'=Evil Shop" in csv_text and "1500.50" in csv_text
    with pytest.raises(DomainError):
        build_report("M1", "x", DateRange.inclusive(date(2025, 1, 1), date(2026, 11, 20)), [], [], NOW)


def test_pdf_renders_and_falls_back_for_non_latin_names():
    r = build_report("M1", "متجر الأمل", PERIOD, [tx("a", A, "1000.00")], [], NOW)
    pdf = render_pdf(r)
    assert pdf.startswith(b"%PDF") and len(pdf) > 1500
