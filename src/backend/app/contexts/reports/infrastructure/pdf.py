"""PDF rendering of the Collections Summary (reportlab canvas, no markup parsing of user text).

Limitation (documented): the built-in PDF fonts cover Latin-1 only, so the PDF is written in French and
a merchant name that cannot be encoded is replaced by the merchant ID rather than printed as boxes.
Arabic PDF output would need an embedded Arabic font and text shaping (future work).
"""

from __future__ import annotations

import io
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.contexts.reports.domain.summary import CollectionsReport
from app.shared.domain.enums import TransactionStatus
from app.shared.domain.money import Money

STATUS_FR = {
    TransactionStatus.ACCEPTED: "Acceptées",
    TransactionStatus.DECLINED: "Refusées",
    TransactionStatus.CANCELLED: "Annulées",
    TransactionStatus.REFUNDED: "Remboursées",
}
CHANNEL_FR = {
    "pos": "TPE / POS",
    "ecommerce": "E-commerce",
    "mobile_app": "Application mobile",
    "contactless": "Sans contact / NFC",
    "bank_transfer": "Virement bancaire",
}


def _latin(text: str, fallback: str) -> str:
    try:
        text.encode("latin-1")
        return text
    except UnicodeEncodeError:
        return fallback


def _dzd(m: Money | None) -> str:
    if m is None:
        return "-"
    whole, _, cents = f"{m.to_decimal():.2f}".partition(".")
    sign = "-" if whole.startswith("-") else ""
    whole = whole.lstrip("-")
    groups = []
    while whole:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    return f"{sign}{' '.join(groups)},{cents} DZD"


def _pct(v: Decimal | None, signed: bool = False) -> str:
    if v is None:
        return "-"
    s = f"{v * 100:+.1f}" if signed else f"{v * 100:.1f}"
    return s.replace(".", ",") + " %"


def render_pdf(r: CollectionsReport) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4, pageCompression=1)
    c.setTitle("CEO-Pay - Synthèse des encaissements")
    c.setAuthor("CEO-Pay")
    w, h = A4
    x, y = 18 * mm, h - 20 * mm

    def text(s: str, size: float = 9, bold: bool = False, color=colors.black, dx: float = 0) -> None:
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.setFillColor(color)
        c.drawString(x + dx, y, s)

    # header: wordmark + title
    c.setFillColor(colors.HexColor("#171717"))
    c.roundRect(x, y - 3 * mm, 9 * mm, 9 * mm, 2 * mm, fill=1, stroke=0)
    # CEO-Pay mark: open "C" + growth arrow (same geometry as the app logo, 32-unit grid)
    u = 9 * mm / 32
    ox, oy = x, y - 3 * mm + 9 * mm  # top-left of the tile; reportlab y grows upwards
    c.setStrokeColor(colors.white)
    c.setLineCap(1)
    c.setLineJoin(1)
    c.setLineWidth(3 * u)
    c.arc(ox + 7.6 * u, oy - 24.4 * u, ox + 24.4 * u, oy - 7.6 * u, 45, 270)
    c.setLineWidth(2.4 * u)
    c.line(ox + 12.8 * u, oy - 19.2 * u, ox + 20.6 * u, oy - 11.4 * u)
    c.line(ox + 15.6 * u, oy - 11.2 * u, ox + 20.8 * u, oy - 11.2 * u)
    c.line(ox + 20.8 * u, oy - 11.2 * u, ox + 20.8 * u, oy - 16.4 * u)
    text("CEO-Pay", 14, True, dx=12 * mm)
    y -= 6 * mm
    text("Synthèse des encaissements", 9, color=colors.HexColor("#525252"), dx=12 * mm)
    y -= 12 * mm
    name = _latin(r.merchant_name, f"Marchand {r.merchant_id}")
    text(f"{name}  ({r.merchant_id})", 11, True)
    y -= 5.5 * mm
    text(
        f"Période : {r.period.start:%d/%m/%Y} - {r.period.last_day:%d/%m/%Y}   ·   comparée au "
        f"{r.previous_period.start:%d/%m/%Y} - {r.previous_period.last_day:%d/%m/%Y}",
        8.5,
        color=colors.HexColor("#525252"),
    )
    y -= 4.5 * mm
    text(
        f"Généré le {r.generated_at:%d/%m/%Y %H:%M}   ·   Devise : DZD   ·   Montants bruts (avant frais)",
        8.5,
        color=colors.HexColor("#525252"),
    )
    y -= 8 * mm
    if r.synthetic:  # never let a synthetic report pass for a statement
        c.setFillColor(colors.HexColor("#fef3c7"))
        c.roundRect(x, y - 2.5 * mm, w - 36 * mm, 8 * mm, 1.5 * mm, fill=1, stroke=0)
        text(
            "DONNÉES DE DÉMONSTRATION SYNTHÉTIQUES - "
            "ce document n'est ni un relevé bancaire ni un relevé SATIM.",
            8,
            True,
            colors.HexColor("#92400e"),
            dx=3 * mm,
        )
        y -= 12 * mm

    k = r.kpis
    kpis = [
        ("Encaissements acceptés", _dzd(k.gross_collected)),
        (
            "Évolution vs période précédente",
            _pct(r.collected_change.pct, True)
            if r.collected_change.pct is not None
            else (
                "nouvelle activité" if r.collected_change.kind.value == "new_activity" else "aucune activité"
            ),
        ),
        ("Transactions acceptées", str(k.accepted_count)),
        (
            "Taux d'acceptation",
            f"{_pct(k.acceptance_rate.value)}  ({k.acceptance_rate.numerator} / "
            f"{k.acceptance_rate.denominator} tentatives)",
        ),
        ("Panier moyen accepté", _dzd(k.average_ticket)),
    ]
    for label, value in kpis:
        text(label, 9, color=colors.HexColor("#525252"))
        text(value, 9, True, dx=75 * mm)
        y -= 6 * mm

    def table(title: str, header: list[str], rows: list[list[str]], cols: list[float]) -> None:
        nonlocal y
        y -= 4 * mm
        text(title, 10, True)
        y -= 6 * mm
        for i, hcell in enumerate(header):
            text(hcell, 8, True, colors.HexColor("#525252"), dx=cols[i] * mm)
        y -= 1.8 * mm
        c.setStrokeColor(colors.HexColor("#e5e5e5"))
        c.line(x, y, w - 18 * mm, y)
        y -= 4.5 * mm
        for row in rows:
            for i, cell in enumerate(row):
                text(cell, 8.5, dx=cols[i] * mm)
            y -= 5.5 * mm

    table(
        "Par statut (statuts jamais additionnés entre eux)",
        ["Statut", "Nombre", "Montant", "Période préc."],
        [
            [
                STATUS_FR[s],
                str(k.by_status[s].count),
                _dzd(k.by_status[s].amount),
                _dzd(r.previous_kpis.by_status[s].amount),
            ]
            for s in TransactionStatus
        ],
        [0, 50, 75, 125],
    )
    table(
        "Par canal",
        ["Canal", "Nombre", "Part (nombre)", "Montant accepté", "Part (montant)"],
        [
            [
                CHANNEL_FR.get(ch.channel.value, ch.channel.value),
                str(ch.count),
                _pct(ch.count_share.value),
                _dzd(ch.accepted_amount),
                _pct(ch.amount_share.value),
            ]
            for ch in r.channels
        ],
        [0, 50, 72, 100, 145],
    )

    y -= 6 * mm
    for line in (
        "Encaissements acceptés = somme des transactions au statut Acceptée. Les refusées, annulées et",
        "remboursées sont présentées séparément. Ce document n'est pas un relevé de règlement : il ne",
        "tient compte ni des frais, ni des délais de règlement, et ne constitue pas un résultat comptable.",
    ):
        text(line, 7.5, color=colors.HexColor("#737373"))
        y -= 4 * mm
    c.setFont("Helvetica", 7)
    c.setFillColor(colors.HexColor("#a3a3a3"))
    c.drawString(
        x, 12 * mm, "CEO-Pay - solution Merchant Pay de l'équipe UMCBOT (défi FINOVIA × ENSM × SATIM)"
    )
    c.showPage()
    c.save()
    return buf.getvalue()
