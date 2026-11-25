"""CSV rendering of the Collections Summary, safe to open in a spreadsheet.

Spreadsheet formula injection: a cell starting with = + - @ (or a tab / carriage return) can be
executed as a formula by Excel / LibreOffice. Every TEXT cell that starts with one of them is
prefixed with an apostrophe. Plain numbers (e.g. "-50.90") are left numeric on purpose.
"""

from __future__ import annotations

import csv
import io
import re

from app.contexts.reports.domain.summary import CollectionsReport
from app.shared.domain.enums import TransactionStatus

_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")
_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")


def neutralize(value: object) -> str:
    text = "" if value is None else str(value)
    if text.startswith(_FORMULA_START) and not _NUMBER.match(text):
        return "'" + text
    return text


def _pct(v) -> str:
    return "" if v is None else f"{v * 100:.2f}"


def render_csv(r: CollectionsReport) -> bytes:
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\r\n")
    row = lambda *cells: w.writerow([neutralize(c) for c in cells])  # noqa: E731
    row("report", "CEO-Pay collections summary")
    row("merchant_id", r.merchant_id)
    row("merchant_name", r.merchant_name)
    row("period_from", r.period.start.isoformat())
    row("period_to", r.period.last_day.isoformat())
    row("compared_with", f"{r.previous_period.start.isoformat()} to {r.previous_period.last_day.isoformat()}")
    row("generated_at", r.generated_at.isoformat(timespec="seconds"))
    row("currency", "DZD")
    row(
        "data",
        "SYNTHETIC DEMO DATA - not a bank or SATIM statement" if r.synthetic else "challenge source data",
    )
    row()
    row("section", "status", "count", "amount_dzd", "previous_count", "previous_amount_dzd")
    for s in TransactionStatus:
        c, p = r.kpis.by_status[s], r.previous_kpis.by_status[s]
        row("status", s.value, c.count, c.amount.to_decimal(), p.count, p.amount.to_decimal())
    row()
    k = r.kpis
    row("indicator", "value", "numerator", "denominator")
    row("gross_accepted_collection_dzd", k.gross_collected.to_decimal(), "", "")
    row("collection_change_pct", _pct(r.collected_change.pct), "", "")
    row(
        "acceptance_rate_pct",
        _pct(k.acceptance_rate.value),
        k.acceptance_rate.numerator,
        k.acceptance_rate.denominator,
    )
    row("average_accepted_ticket_dzd", k.average_ticket.to_decimal() if k.average_ticket else "", "", "")
    row()
    row("section", "channel", "count", "count_share_pct", "accepted_amount_dzd", "amount_share_pct")
    for ch in r.channels:
        row(
            "channel",
            ch.channel.value,
            ch.count,
            _pct(ch.count_share.value),
            ch.accepted_amount.to_decimal(),
            _pct(ch.amount_share.value),
        )
    return ("\ufeff" + out.getvalue()).encode("utf-8")  # BOM: Excel opens accents correctly
