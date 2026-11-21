"""Synthetic layouts only: no real statement text."""
import combine_statements
import statement_pdf

HEADER = " Date     Description                       £ Out          £ In      £ Balance"
TEXT = "\n".join([
    HEADER,
    " 2025     Balance from statement 1 dated 11/12/2025                       100.00",
    " 30 Dec   Contactless Payment                   3.55",
    "          SHOP ONE TOWN",
    "          PIONEER.NET TALLINN                   6.68",
    "          9.000000USD at 1.34731",
    "          Foreign currency transaction fee      0.20                     89.57",
    " 2026",
    " 02 Jan   Bank credit EMPLOYER LTD                          50.00      139.57",
    "          REF 123",
    "          Effective Date 01 Jan 2026",
    " 05 Jan",
    "          Direct debit COUNCIL",
    "          Transfer to A Person",
    "                                               20.00",
    "                                               10.00",
    "                                                                       119.57",
    "Please check your statement",
])


def test_parse_reconciles_and_joins_lines():
    rows, opening, checks = statement_pdf.parse_text(TEXT)
    assert opening == 100.00
    assert [r["amount"] for r in rows] == [-3.55, -6.68, -0.20, 50.00, -20.00, -10.00]
    assert [r["date"] for r in rows] == ["2025-12-30"] * 3 + ["2026-01-02"] + ["2026-01-05"] * 2
    assert rows[0]["description"] == "Contactless Payment | SHOP ONE TOWN"
    assert rows[4]["description"] == "Direct debit COUNCIL"
    assert statement_pdf.split(rows[0]["description"]) == ("Contactless Payment", "SHOP ONE TOWN")
    assert statement_pdf.reconcile(rows, opening, checks) == []


def test_reconcile_catches_a_wrong_amount():
    rows, opening, checks = statement_pdf.parse_text(TEXT)
    rows[1]["amount"] = -6.00
    assert statement_pdf.reconcile(rows, opening, checks)


def test_combine_pairs_own_transfers():
    main = [{"date": "2026-01-02", "kind": "Transfer to", "merchant": "Jo Bloggs", "description": "", "amount": "-100.0"},
            {"date": "2026-01-03", "kind": "Direct debit", "merchant": "COUNCIL", "description": "", "amount": "-20.0"}]
    monzo = [{"date": "2026-01-03", "time": "09:00", "merchant": "BLOGGS JO", "note": "", "amount": 100.0, "category": "transfers"},
             {"date": "2026-01-03", "time": "10:00", "merchant": "Shop", "note": "", "amount": -5.0, "category": "groceries"}]
    rows, paired = combine_statements.combine(main, monzo, "bloggs")
    assert paired == 1
    assert sorted((r["merchant"], r["internal"]) for r in rows) == [
        ("BLOGGS JO", True), ("COUNCIL", False), ("Jo Bloggs", True), ("Shop", False)]
