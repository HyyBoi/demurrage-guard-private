"""Tests for the DemurrageGuard engine. Run:  python -m pytest -q"""

from engine import logic

HERO = {  # Invoice A: the demo story
    "carrier": "OCEANIC LINE LTD.",
    "invoice_number": "OCL-DD-2026-10-0147",
    "invoice_date": "2026-10-01",
    "container_id": "OLCU 482193-7",
    "charge_start": "2026-09-06",
    "charge_end": "2026-09-14",
    "rate_per_day": "$175.00",
    "billed_days": 9,
    "total_amount": "1,575.00",
    "currency": "USD",
}
CLEAN = {  # Invoice B
    "carrier": "Oceanic Line", "invoice_number": "OCL-DD-2026-10-0233", "invoice_date": "2026-10-05",
    "container_id": "OLCU5530128", "charge_start": "2026-09-21", "charge_end": "2026-09-25",
    "rate_per_day": 175, "billed_days": 5, "total_amount": 875, "currency": "USD",
}
LATE = {  # Invoice C
    "carrier": "Oceanic Line", "invoice_number": "OCL-DD-2026-09-0612", "invoice_date": "2026-09-20",
    "container_id": "OLCU7719402", "charge_start": "2026-07-13", "charge_end": "2026-07-15",
    "rate_per_day": 175, "billed_days": 3, "total_amount": 525, "currency": "USD",
}
AS_OF = "2026-10-10"


def test_hero_invoice_overcharged():
    r = logic.audit_invoice(HERO, AS_OF)
    assert r["ok"] is True
    assert r["billed_days"] == 9 and r["billed_amount"] == 1575
    assert r["correct_days"] == 4 and r["correct_amount"] == 700
    assert r["overcharge"] == 875
    assert r["chargeable_dates"] == ["2026-09-09", "2026-09-10", "2026-09-11", "2026-09-14"]
    assert r["verdict"] == "overcharged" and r["recommendation"] == "dispute_full"
    # The 9 billed days, 5 of them wrongly billed
    billed = [x for x in r["day_table"] if x["billed"]]
    assert [x["date"][-2:] for x in billed] == ["06", "07", "08", "09", "10", "11", "12", "13", "14"]
    wrong = {x["date"]: x["status"] for x in billed if x["wrongly_billed"]}
    assert wrong == {"2026-09-06": "weekend", "2026-09-07": "holiday", "2026-09-08": "free",
                     "2026-09-12": "weekend", "2026-09-13": "weekend"}
    # Free days 1..5 = Sep 1, 2, 3, 4, 8
    free = [x["date"] for x in r["day_table"] if x["status"] == "free"]
    assert free == ["2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04", "2026-09-08"]
    # FMC: valid, dispute window closes Oct 31 -> 21 days left on Oct 10
    assert r["fmc"]["valid"] is True
    assert r["fmc"]["dispute_deadline"] == "2026-10-31" and r["fmc"]["days_remaining"] == 21
    assert "Overcharged by $875" in r["verdict_html"]


def test_clean_invoice_pay():
    r = logic.audit_invoice(CLEAN, AS_OF)
    assert r["ok"] and r["verdict"] == "correct"
    assert r["overcharge"] == 0 and r["recommendation"] == "pay"
    assert r["correct_days"] == 5


def test_late_invoice_invalid_under_fmc():
    r = logic.audit_invoice(LATE, AS_OF)
    assert r["ok"]
    assert r["fmc"]["valid"] is False and r["fmc"]["days_late"] == 37
    assert r["verdict"] == "invalid_fmc" and r["recommendation"] == "dispute_full"
    assert r["overcharge"] == 0  # day count is right ...
    assert r["disputable_amount"] == 525  # ... but the whole invoice is invalid


def test_unknown_carrier_and_missing_container_clean_errors():
    r = logic.audit_invoice({**HERO, "carrier": "Blue Whale Shipping"}, AS_OF)
    assert r["ok"] is False and r["error"]["code"] == "UNKNOWN_CARRIER"
    r = logic.audit_invoice({**HERO, "container_id": "ABCU0000000"}, AS_OF)
    assert r["ok"] is False and r["error"]["code"] == "CONTAINER_NOT_FOUND"
    r = logic.audit_invoice({"carrier": "Oceanic Line"}, AS_OF)
    assert r["ok"] is False and r["error"]["code"] == "MISSING_FIELDS"
    assert "container_id" in r["error"]["missing_fields"]
    r = logic.audit_invoice({**HERO, "invoice_date": "sometime in october"}, AS_OF)
    assert r["ok"] is False and r["error"]["code"] == "INVALID_DATE"
    r = logic.audit_invoice(None, AS_OF)
    assert r["ok"] is False


def test_messy_llm_formats_are_parsed():
    messy = {**HERO, "invoice_date": "Oct 1, 2026", "charge_start": "09/06/2026", "charge_end": "14 Sep 2026",
             "rate_per_day": "USD 175", "total_amount": "$1,575.00", "billed_days": "9 days"}
    r = logic.audit_invoice({"output": messy}, AS_OF)
    assert r["ok"] and r["overcharge"] == 875


def test_port_closure_excluded():
    inv = {"carrier": "Pacific Star", "invoice_number": "PSL-1", "invoice_date": "2026-07-01",
           "container_id": "PSLU3308815", "charge_start": "2026-06-19", "charge_end": "2026-06-24",
           "rate_per_day": 150, "billed_days": 6, "total_amount": 900}
    r = logic.audit_invoice(inv, AS_OF)
    assert r["ok"]
    # free: Jun 15-18 (4); Jun 19 holiday; 20-21 weekend; 22 closure; chargeable 23, 24
    assert r["chargeable_dates"] == ["2026-06-23", "2026-06-24"]
    assert r["overcharge"] == 600
    assert r["fmc"]["window_open"] is False  # Jul 31 deadline already passed on Oct 10


def test_letter_guard():
    r = logic.audit_invoice(HERO, AS_OF)
    facts = logic.letter_facts(r, "partial", 400, "Our trucker was late on Sep 14.")
    assert facts["disputed_amount"] == 400 and facts["amount_to_pay"] == 1175
    letter = logic.template_letter(facts)
    assert logic.check_letter(letter, facts)["ok"]
    bad = letter + "\nWe also expect $99,999 compensation."
    g = logic.check_letter(bad, facts)
    assert not g["ok"] and "$99,999" in g["unknown_amounts"]
