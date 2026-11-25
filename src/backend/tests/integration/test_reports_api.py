"""Reports over HTTP: reconciled with collections, merchant-scoped, safe headers, export audit."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEventRow

API = "/api/v1/reports/collections-summary"
PERIOD = {"date_from": "2026-11-01", "date_to": "2026-11-20"}


def test_preview_reconciles_with_collections_summary(login):
    c = login()
    r = c.get(API, params=PERIOD)
    assert r.status_code == 200 and r.headers["cache-control"].startswith("no-store")
    rep = r.json()
    s = c.get("/api/v1/collections/summary", params={"a_from": "2026-11-01", "a_to": "2026-11-20"}).json()
    assert rep["gross_collected"] == s["collected_a"]
    assert {x["status"]: x["amount"] for x in rep["statuses"]} == {
        x["status"]: x["amount_a"] for x in s["by_status"]
    }
    assert rep["acceptance_rate"] == s["acceptance_rate_a"] and rep["currency"] == "DZD"
    assert rep["merchant_id"] == "M1" and rep["synthetic"] is False
    assert rep["pdf_filename"] == "ceo-pay_collections_M1_2026-11-01_2026-11-20.pdf"


def test_files_are_scoped_safe_and_export_is_audited(login, seeded):
    c = login()
    c.patch("/api/v1/merchant/me", json={"display_name": '=HYPERLINK("http://evil")'})
    csv = c.get(f"{API}.csv", params=PERIOD)
    assert csv.status_code == 200 and csv.headers["content-type"].startswith("text/csv")
    assert (
        'attachment; filename="ceo-pay_collections_M1_2026-11-01_2026-11-20.csv"'
        == csv.headers["content-disposition"]
    )
    text = csv.content.decode("utf-8")
    assert "'=HYPERLINK" in text and "99999" not in text  # neutralised; M2's sale absent
    pdf = c.get(f"{API}.pdf", params=PERIOD)
    assert (
        pdf.status_code == 200
        and pdf.content.startswith(b"%PDF")
        and pdf.headers["cache-control"].startswith("no-store")
    )
    with Session(seeded) as s:
        refs = s.scalars(
            select(AuditEventRow.entity_ref).where(AuditEventRow.action == "report.exported")
        ).all()
    assert len(refs) == 2 and all(
        "merchant:M1" in r and "DZD" not in r for r in refs
    )  # no figures in the audit
    c.get(API, params=PERIOD)  # a preview is not an export
    with Session(seeded) as s:
        assert (
            len(s.scalars(select(AuditEventRow).where(AuditEventRow.action == "report.exported")).all()) == 2
        )


def test_other_merchant_and_anonymous_and_bad_periods(client, login):
    assert client.get(API).status_code == 401 and client.get(f"{API}.pdf").status_code == 401
    other = login("two@test.dz", "pw-two").get(API, params=PERIOD).json()
    assert other["merchant_id"] == "M2" and other["gross_collected"]["amount"] == "99999.00"
    c = login()
    assert c.get(API, params={"date_from": "2026-11-20", "date_to": "2026-11-01"}).status_code == 422
    assert c.get(API, params={"date_from": "2024-01-01", "date_to": "2026-11-20"}).status_code == 422
    assert c.get(API, params={"date_from": "not-a-date"}).status_code == 422
