"""DemurrageGuard calculation engine.

Pure, deterministic functions. No AI, no network. Every number shown to the
user (days, money, deadlines) comes from here, never from a language model.

Rules implemented
-----------------
Free time   Counts only non-excluded days, starting on the discharge day (Day 1).
            Excluded days = weekends, the port's public holidays and port
            closures (as listed in the carrier contract).
Chargeable  After free time is used up, every later non-excluded day up to and
            including the gate-out day is chargeable at the contract rate.
FMC         US Federal Maritime Commission demurrage & detention billing rule
            (46 CFR Part 541): an invoice must be issued within 30 calendar
            days of the date charges were last incurred, and the billed party
            has 30 calendar days from the invoice date to dispute it.
"""

from __future__ import annotations

import html
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent / "data"
FMC_ISSUE_DAYS = 30
FMC_DISPUTE_DAYS = 30

_DATE_FORMATS = [
    "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
    "%b %d, %Y", "%B %d, %Y", "%b %d %Y", "%B %d %Y",
    "%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%d-%b-%y", "%d %b, %Y",
    "%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y",
    "%a, %b %d, %Y", "%A, %B %d, %Y",
]


class EngineError(Exception):
    """A clean, user-facing error. Never a crash."""

    def __init__(self, code: str, message: str, **extra: Any):
        super().__init__(message)
        self.code = code
        self.message = message
        self.extra = extra

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, **self.extra}


# --------------------------------------------------------------------------
# Data access
# --------------------------------------------------------------------------

def _load(name: str) -> dict:
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


CONTRACTS = _load("contracts.json")["carriers"]
GATE_EVENTS = _load("gate_events.json")["containers"]
HOLIDAYS = _load("holidays.json")["ports"]


def _norm_text(s: str) -> str:
    s = re.sub(r"[^a-z0-9 ]+", " ", str(s).lower())
    return re.sub(r"\s+", " ", s).strip()


def normalize_container(container_id: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(container_id or "").upper())


def resolve_carrier(carrier: Any) -> str | None:
    """Map a free-text carrier name from an invoice to a contract key."""
    if not carrier:
        return None
    text = _norm_text(carrier)
    if not text:
        return None
    for key, c in CONTRACTS.items():
        names = {_norm_text(key.replace("_", " ")), _norm_text(c["name"])}
        names |= {_norm_text(a) for a in c.get("aliases", [])}
        if text in names:
            return key
    # Looser match: a known name appears inside the invoice text
    # ("OCEANIC LINE LTD. - LOS ANGELES"). Short aliases need a word match.
    for key, c in CONTRACTS.items():
        names = [_norm_text(c["name"])] + [_norm_text(a) for a in c.get("aliases", [])]
        for n in names:
            if len(n) >= 6 and n in text:
                return key
            if len(n) < 6 and n in text.split():
                return key
    return None


def get_contract(carrier: str) -> dict:
    key = resolve_carrier(carrier)
    if key is None:
        raise EngineError(
            "UNKNOWN_CARRIER",
            f"No contract on file for carrier '{carrier}'. Known carriers: "
            + ", ".join(c["name"] for c in CONTRACTS.values()) + ".",
        )
    return {"carrier_key": key, **{k: v for k, v in CONTRACTS[key].items() if k != "aliases"}}


def get_gate_events(container_id: str) -> dict:
    cid = normalize_container(container_id)
    rec = GATE_EVENTS.get(cid)
    if rec is None:
        raise EngineError(
            "CONTAINER_NOT_FOUND",
            f"No terminal gate records for container '{container_id}'. "
            "Check the container number on the invoice.",
        )
    return {"container_id": cid, **rec}


def get_calendar(port: str, start: Any, end: Any) -> list[dict]:
    """Every day from start to end (inclusive) with why it is or isn't a working day."""
    s, e = parse_date(start, "start"), parse_date(end, "end")
    if e < s:
        raise EngineError("INVALID_RANGE", f"End date {e} is before start date {s}.")
    if (e - s).days > 370:
        raise EngineError("INVALID_RANGE", "Date range is longer than a year; check the dates.")
    p = HOLIDAYS.get(port, {"holidays": {}, "port_closures": {}})
    out = []
    d = s
    while d <= e:
        out.append(_classify_calendar_day(d, p))
        d += timedelta(days=1)
    return out


def _classify_calendar_day(d: date, port_cal: dict) -> dict:
    iso = d.isoformat()
    if iso in port_cal.get("port_closures", {}):
        kind, reason = "port_closure", port_cal["port_closures"][iso]
    elif iso in port_cal.get("holidays", {}):
        kind, reason = "holiday", port_cal["holidays"][iso]
    elif d.weekday() >= 5:
        kind, reason = "weekend", d.strftime("%A")
    else:
        kind, reason = "working_day", ""
    return {"date": iso, "weekday": d.strftime("%a"), "kind": kind, "reason": reason}


# --------------------------------------------------------------------------
# Parsing helpers (LLM output is messy; be forgiving, never guess)
# --------------------------------------------------------------------------

def parse_date(value: Any, field: str = "date") -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None or str(value).strip() == "" or str(value).strip().lower() in {"null", "none", "n/a"}:
        raise EngineError("MISSING_FIELDS", f"'{field}' is missing.", missing_fields=[field])
    s = re.sub(r"\s+", " ", str(value).strip())
    s = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", s)  # 1st -> 1
    s = s.split("T")[0] if re.match(r"^\d{4}-\d{2}-\d{2}T", s) else s
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise EngineError("INVALID_DATE", f"Could not read '{field}' = '{value}' as a date.", field=field)


def parse_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if s == "" or s.lower() in {"null", "none", "n/a"}:
        return None
    s = re.sub(r"(?i)usd|us\$|\$|days?|per day|/day", "", s).replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _is_blank(v: Any) -> bool:
    return v is None or (isinstance(v, str) and v.strip().lower() in {"", "null", "none", "n/a"})


def money(x: float) -> str:
    return f"${x:,.2f}" if abs(x - round(x)) > 1e-9 else f"${x:,.0f}"


# --------------------------------------------------------------------------
# FMC rule
# --------------------------------------------------------------------------

def check_fmc_window(invoice_date: Any, last_charge_date: Any, as_of_date: Any = None) -> dict:
    inv = parse_date(invoice_date, "invoice_date")
    last = parse_date(last_charge_date, "last_charge_date")
    as_of = parse_date(as_of_date, "as_of_date") if not _is_blank(as_of_date) else date.today()

    issue_deadline = last + timedelta(days=FMC_ISSUE_DAYS)
    valid = inv <= issue_deadline
    days_late = max(0, (inv - issue_deadline).days)
    dispute_deadline = inv + timedelta(days=FMC_DISPUTE_DAYS)
    days_remaining = (dispute_deadline - as_of).days

    if valid:
        reason = (f"Invoice issued {(inv - last).days} days after charges were last incurred "
                  f"(limit {FMC_ISSUE_DAYS}).")
    else:
        reason = (f"Invoice issued {(inv - last).days} days after charges were last incurred on {last}. "
                  f"FMC rules require billing within {FMC_ISSUE_DAYS} days (by {issue_deadline}), "
                  f"so the carrier may not collect these charges.")

    return {
        "rule": "46 CFR Part 541 (FMC demurrage & detention billing)",
        "valid": valid,
        "invoice_date": inv.isoformat(),
        "last_charge_date": last.isoformat(),
        "issue_deadline": issue_deadline.isoformat(),
        "days_late": days_late,
        "as_of_date": as_of.isoformat(),
        "dispute_deadline": dispute_deadline.isoformat(),
        "days_remaining": days_remaining,
        "window_open": days_remaining >= 0,
        "reason": reason,
    }


# --------------------------------------------------------------------------
# The audit
# --------------------------------------------------------------------------

REQUIRED = ["carrier", "container_id", "invoice_date"]
STATUS_LABELS = {
    "before_discharge": "Not yet discharged",
    "free": "Free time",
    "weekend": "Weekend (excluded)",
    "holiday": "Public holiday (excluded)",
    "port_closure": "Port closure (excluded)",
    "chargeable": "Chargeable",
    "after_gate_out": "Container already gone",
}


def _normalize_invoice(raw: dict) -> dict:
    raw = raw or {}
    if not isinstance(raw, dict):
        raise EngineError("INVALID_INPUT", "Invoice must be a JSON object.")
    # Accept a nested {"invoice": {...}} or an LLM {"output": {...}} wrapper.
    for wrapper in ("invoice", "output"):
        if isinstance(raw.get(wrapper), dict) and "carrier" not in raw:
            raw = raw[wrapper]
    return {
        "carrier": None if _is_blank(raw.get("carrier")) else str(raw.get("carrier")).strip(),
        "invoice_number": None if _is_blank(raw.get("invoice_number")) else str(raw.get("invoice_number")).strip(),
        "invoice_date": raw.get("invoice_date"),
        "container_id": None if _is_blank(raw.get("container_id")) else str(raw.get("container_id")).strip(),
        "charge_start": raw.get("charge_start"),
        "charge_end": raw.get("charge_end"),
        "rate_per_day": parse_number(raw.get("rate_per_day")),
        "billed_days": parse_number(raw.get("billed_days")),
        "total_amount": parse_number(raw.get("total_amount")),
        "currency": None if _is_blank(raw.get("currency")) else str(raw.get("currency")).strip().upper(),
    }


def audit_invoice(invoice: dict, as_of_date: Any = None) -> dict:
    """Run every check. Always returns a dict; never raises for bad input."""
    try:
        return _audit(invoice, as_of_date)
    except EngineError as e:
        try:
            echo = _normalize_invoice(invoice)
        except EngineError:
            echo = None
        return {"ok": False, "error": e.to_dict(), "invoice": echo}
    except Exception as e:  # last-resort safety net: report, don't crash
        return {"ok": False, "error": {"code": "INTERNAL_ERROR", "message": f"Unexpected error: {e}"},
                "invoice": None}


def _audit(raw: dict, as_of_date: Any) -> dict:
    inv = _normalize_invoice(raw)

    missing = [f for f in REQUIRED if _is_blank(inv[f])]
    has_range = not _is_blank(inv["charge_start"]) and not _is_blank(inv["charge_end"])
    if not has_range and inv["billed_days"] is None:
        missing.append("charge_start/charge_end or billed_days")
    if missing:
        raise EngineError("MISSING_FIELDS",
                          "The invoice is missing information needed for the audit: " + ", ".join(missing) + ".",
                          missing_fields=missing)

    contract = get_contract(inv["carrier"])
    gate = get_gate_events(inv["container_id"])
    if gate["carrier"] != contract["carrier_key"]:
        owner = CONTRACTS[gate["carrier"]]["name"]
        raise EngineError(
            "CONTAINER_CARRIER_MISMATCH",
            f"Container {gate['container_id']} belongs to {owner} in our gate records, "
            f"but this invoice is from {contract['name']}. Check the invoice before paying.",
        )

    invoice_date = parse_date(inv["invoice_date"], "invoice_date")
    discharge = parse_date(gate["discharge_date"], "discharge_date")
    gate_out = parse_date(gate["gate_out_date"], "gate_out_date")

    assumptions: list[str] = []
    if has_range:
        c_start = parse_date(inv["charge_start"], "charge_start")
        c_end = parse_date(inv["charge_end"], "charge_end")
        if c_end < c_start:
            raise EngineError("INVALID_RANGE", f"Charge period ends ({c_end}) before it starts ({c_start}).")
    else:
        # Only billed_days known: assume the carrier billed consecutive calendar
        # days ending at gate-out. Flagged so the human can see the assumption.
        n = int(inv["billed_days"])
        if n <= 0:
            raise EngineError("MISSING_FIELDS", "Billed days must be a positive number.",
                              missing_fields=["billed_days"])
        c_end = parse_date(inv["charge_end"], "charge_end") if not _is_blank(inv["charge_end"]) else gate_out
        c_start = c_end - timedelta(days=n - 1)
        assumptions.append(f"Invoice gave no charge period; assumed {n} calendar days ending {c_end}.")

    range_days = (c_end - c_start).days + 1
    billed_days = int(inv["billed_days"]) if inv["billed_days"] is not None else range_days
    contract_rate = float(contract["rate_per_day"])
    billed_rate = inv["rate_per_day"] if inv["rate_per_day"] is not None else contract_rate
    if inv["rate_per_day"] is None:
        assumptions.append(f"Invoice gave no daily rate; used contract rate {money(contract_rate)}.")
    billed_amount = inv["total_amount"] if inv["total_amount"] is not None else round(billed_days * billed_rate, 2)
    if inv["total_amount"] is None:
        assumptions.append("Invoice gave no total; used billed days x rate.")

    # ---- day-by-day table -------------------------------------------------
    port_cal = HOLIDAYS.get(contract["port"], {"holidays": {}, "port_closures": {}})
    start = min(discharge, c_start)
    end = max(gate_out, c_end)
    if (end - start).days > 370:
        raise EngineError("INVALID_RANGE", "Charge period is longer than a year; check the invoice dates.")

    free_used = 0
    rows = []
    d = start
    while d <= end:
        cal = _classify_calendar_day(d, port_cal)
        billed = c_start <= d <= c_end
        free_no = None
        if d < discharge:
            status, reason = "before_discharge", f"Container discharged on {discharge}"
        elif d > gate_out:
            status, reason = "after_gate_out", f"Container left the terminal on {gate_out}"
        elif cal["kind"] != "working_day":
            status, reason = cal["kind"], cal["reason"]
        elif free_used < contract["free_days"]:
            free_used += 1
            free_no = free_used
            status, reason = "free", f"Free day {free_used} of {contract['free_days']}"
        else:
            status, reason = "chargeable", "Free time used up"
        correct = contract_rate if status == "chargeable" else 0.0
        rows.append({
            "date": d.isoformat(),
            "weekday": d.strftime("%a"),
            "status": status,
            "label": STATUS_LABELS[status],
            "reason": reason,
            "free_day": free_no,
            "billed": billed,
            "billed_charge": round(billed_rate, 2) if billed else 0.0,
            "correct_charge": correct,
            "wrongly_billed": billed and status != "chargeable",
        })
        d += timedelta(days=1)

    correct_rows = [r for r in rows if r["status"] == "chargeable"]
    correct_days = len(correct_rows)
    correct_amount = round(correct_days * contract_rate, 2)
    overcharge = round(billed_amount - correct_amount, 2)

    # ---- FMC --------------------------------------------------------------
    fmc = check_fmc_window(invoice_date, c_end, as_of_date)

    # ---- findings (evidence for the human and the letter) ----------------
    findings: list[dict] = []

    def add(code: str, severity: str, text: str, dates: list[str] | None = None, amount: float | None = None):
        findings.append({"code": code, "severity": severity, "text": text,
                         "dates": dates or [], "amount": amount})

    if not fmc["valid"]:
        add("FMC_LATE_INVOICE", "high", fmc["reason"], [fmc["invoice_date"]], billed_amount)
    by_status: dict[str, list[dict]] = {}
    for r in rows:
        if r["wrongly_billed"]:
            by_status.setdefault(r["status"], []).append(r)
    descriptions = {
        "weekend": "Weekend days billed, but the contract excludes weekends",
        "holiday": "Public holidays billed, but the contract excludes them",
        "port_closure": "Port-closure days billed, but the contract excludes them",
        "free": "Contractual free-time days billed",
        "after_gate_out": "Days billed after the container had already left the terminal",
        "before_discharge": "Days billed before the container was even discharged",
    }
    for status in ["free", "weekend", "holiday", "port_closure", "after_gate_out", "before_discharge"]:
        rs = by_status.get(status)
        if rs:
            ds = [r["date"] for r in rs]
            detail = ", ".join(f"{_fmt_day(r['date'])}" + (f" ({r['reason']})" if status in ("holiday", "port_closure") else "")
                               for r in rs)
            add(f"BILLED_{status.upper()}", "high",
                f"{descriptions[status]}: {detail}.", ds, round(len(rs) * billed_rate, 2))
    if abs(billed_rate - contract_rate) > 0.005:
        add("RATE_MISMATCH", "high",
            f"Invoice rate {money(billed_rate)}/day differs from the contract rate {money(contract_rate)}/day "
            f"(contract {contract['contract_id']}).")
    if inv["billed_days"] is not None and billed_days != range_days:
        add("DAYS_MISMATCH", "medium",
            f"Invoice says {billed_days} days, but the charge period {c_start} to {c_end} is {range_days} days.")
    if inv["total_amount"] is not None and abs(billed_days * billed_rate - billed_amount) > 0.5:
        add("ARITHMETIC_ERROR", "medium",
            f"Invoice total {money(billed_amount)} does not equal {billed_days} days x {money(billed_rate)} "
            f"= {money(billed_days * billed_rate)}.")
    if fmc["valid"] and not fmc["window_open"]:
        add("DISPUTE_WINDOW_CLOSED", "high",
            f"The 30-day dispute window closed on {fmc['dispute_deadline']}.")
    elif fmc["window_open"] and fmc["days_remaining"] <= 7:
        add("DISPUTE_WINDOW_CLOSING", "medium",
            f"Only {fmc['days_remaining']} days left to dispute (deadline {fmc['dispute_deadline']}).")
    missed = [r for r in correct_rows if not r["billed"]]
    if missed:
        add("UNBILLED_CHARGEABLE_DAYS", "info",
            "Chargeable days the carrier did not bill: " + ", ".join(_fmt_day(r["date"]) for r in missed) + ".",
            [r["date"] for r in missed])

    # ---- verdict + rule-based recommendation ------------------------------
    if not fmc["valid"]:
        verdict = "invalid_fmc"
        headline = f"Invoice invalid under FMC rules: {money(billed_amount)} not payable"
        recommendation = "dispute_full"
        rec_reason = ("The carrier billed too late. Under FMC rules the whole invoice can be disputed, "
                      "regardless of whether the day count is right.")
        disputable = billed_amount
    elif overcharge > 0.005:
        verdict = "overcharged"
        headline = f"Overcharged by {money(overcharge)}"
        recommendation = "dispute_full"
        rec_reason = (f"The contract supports a bill of {money(correct_amount)} ({correct_days} chargeable days), "
                      f"not {money(billed_amount)}. Every excluded day is backed by the contract and gate records.")
        disputable = overcharge
    elif overcharge < -0.005:
        verdict = "undercharged"
        headline = f"Carrier billed {money(-overcharge)} less than the contract allows"
        recommendation = "pay"
        rec_reason = "The invoice is lower than the contractual amount. Paying as billed is in your favour."
        disputable = 0.0
    else:
        verdict = "correct"
        headline = f"Invoice is correct: {money(billed_amount)}"
        recommendation = "pay"
        rec_reason = "Billed days and amount match the contract, gate records and calendar."
        disputable = 0.0

    result = {
        "ok": True,
        "verdict": verdict,
        "headline": headline,
        "recommendation": recommendation,
        "recommendation_reason": rec_reason,
        "currency": contract["currency"],
        "billed_days": billed_days,
        "billed_rate": billed_rate,
        "billed_amount": round(billed_amount, 2),
        "correct_days": correct_days,
        "contract_rate": contract_rate,
        "correct_amount": correct_amount,
        "overcharge": overcharge,
        "disputable_amount": round(disputable, 2),
        "amount_to_pay_if_upheld": 0.0 if verdict == "invalid_fmc" else min(round(billed_amount, 2), correct_amount),
        "chargeable_dates": [r["date"] for r in correct_rows],
        "charge_period": {"start": c_start.isoformat(), "end": c_end.isoformat(), "calendar_days": range_days},
        "fmc": fmc,
        "findings": findings,
        "assumptions": assumptions,
        "contract": contract,
        "gate_events": gate,
        "invoice": {**inv, "invoice_date": invoice_date.isoformat(),
                    "charge_start": c_start.isoformat(), "charge_end": c_end.isoformat(),
                    "container_id": gate["container_id"]},
        "day_table": rows,
    }
    result["summary_text"] = summary_text(result)
    result["verdict_html"] = verdict_html(result)
    result["verdict_form_html"] = verdict_form_html(result)
    return result


def _fmt_day(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.strftime('%a')} {d.strftime('%b')} {d.day}"


# --------------------------------------------------------------------------
# Presentation (deterministic, so the UI never depends on an LLM)
# --------------------------------------------------------------------------

def summary_text(r: dict) -> str:
    inv = r["invoice"]
    lines = [
        f"{r['headline']}.",
        f"Invoice {inv.get('invoice_number') or '(no number)'} from {r['contract']['name']} for container "
        f"{inv['container_id']}: billed {r['billed_days']} days = {money(r['billed_amount'])}.",
        f"Contract {r['contract']['contract_id']}: {r['contract']['free_days']} free working days, "
        f"then {money(r['contract_rate'])}/day. Correct charge: {r['correct_days']} days = {money(r['correct_amount'])}.",
    ]
    for f in r["findings"]:
        lines.append(f"- {f['text']}")
    fmc = r["fmc"]
    if fmc["window_open"]:
        lines.append(f"Dispute window closes {fmc['dispute_deadline']} ({fmc['days_remaining']} days left).")
    else:
        lines.append(f"Dispute window closed {fmc['dispute_deadline']}.")
    return "\n".join(lines)


_STATUS_COLORS = {
    "chargeable": ("#fde8e8", "#9b1c1c"),
    "free": ("#e6f4ea", "#1e6b34"),
    "weekend": ("#eef1f5", "#3f4a5a"),
    "holiday": ("#fff4dc", "#8a5a00"),
    "port_closure": ("#fff4dc", "#8a5a00"),
    "after_gate_out": ("#f3e8ff", "#5b21b6"),
    "before_discharge": ("#f3e8ff", "#5b21b6"),
}


def verdict_html(r: dict) -> str:
    e = html.escape
    fmc = r["fmc"]
    bad = r["verdict"] in ("overcharged", "invalid_fmc")
    head_bg, head_fg = ("#fde8e8", "#9b1c1c") if bad else ("#e6f4ea", "#1e6b34")
    if fmc["window_open"]:
        badge_bg = "#fde8e8" if fmc["days_remaining"] <= 7 else "#fff4dc"
        badge = f"Dispute window closes in {fmc['days_remaining']} days ({_fmt_day(fmc['dispute_deadline'])})"
    else:
        badge_bg = "#eef1f5"
        badge = f"Dispute window closed on {_fmt_day(fmc['dispute_deadline'])}"
    fmc_line = ("FMC 30-day billing rule: passed" if fmc["valid"]
                else f"FMC 30-day billing rule: FAILED ({fmc['days_late']} days late)")

    rows_html = []
    for row in r["day_table"]:
        bg, fg = _STATUS_COLORS[row["status"]]
        mark = ""
        if row["wrongly_billed"]:
            mark = "<b style='color:#9b1c1c'>Billed, not owed</b>"
        elif row["billed"]:
            mark = "Billed, owed"
        elif row["status"] == "chargeable":
            mark = "Owed, not billed"
        rows_html.append(
            f"<tr style='background:{bg};color:{fg}'>"
            f"<td style='padding:4px 8px'>{e(_fmt_day(row['date']))}</td>"
            f"<td style='padding:4px 8px'><b>{e(row['label'])}</b><br><small>{e(row['reason'])}</small></td>"
            f"<td style='padding:4px 8px;text-align:right'>{money(row['billed_charge']) if row['billed'] else '-'}</td>"
            f"<td style='padding:4px 8px;text-align:right'>{money(row['correct_charge']) if row['correct_charge'] else '-'}</td>"
            f"<td style='padding:4px 8px'>{mark}</td></tr>"
        )
    findings = "".join(f"<li>{e(f['text'])}</li>" for f in r["findings"] if f["severity"] != "info")
    rec_label = {"dispute_full": "Dispute in full", "pay": "Pay invoice"}[r["recommendation"]]
    inv = r["invoice"]
    return (
        "<div style='font-family:system-ui,Segoe UI,Arial,sans-serif;font-size:14px;line-height:1.4'>"
        f"<div style='background:{head_bg};color:{head_fg};padding:12px 14px;border-radius:8px'>"
        f"<div style='font-size:20px;font-weight:700'>{e(r['headline'])}</div>"
        f"<div>Billed {r['billed_days']} days = {money(r['billed_amount'])} &nbsp;|&nbsp; "
        f"Contract says {r['correct_days']} days = {money(r['correct_amount'])}</div></div>"
        f"<div style='margin:8px 0;padding:8px 12px;border-radius:8px;background:{badge_bg}'>"
        f"<b>{e(badge)}</b> &nbsp;&middot;&nbsp; {e(fmc_line)}</div>"
        f"<p style='margin:6px 0'><b>{e(r['contract']['name'])}</b> &middot; invoice {e(inv.get('invoice_number') or '-')} "
        f"&middot; container {e(inv['container_id'])} &middot; discharged {e(_fmt_day(r['gate_events']['discharge_date']))}, "
        f"gate-out {e(_fmt_day(r['gate_events']['gate_out_date']))} &middot; contract {e(r['contract']['contract_id'])}: "
        f"{r['contract']['free_days']} free working days, {money(r['contract_rate'])}/day</p>"
        "<table style='border-collapse:collapse;width:100%;font-size:13px'>"
        "<tr style='text-align:left;border-bottom:2px solid #999'><th style='padding:4px 8px'>Day</th>"
        "<th style='padding:4px 8px'>Status (code-verified)</th><th style='padding:4px 8px;text-align:right'>Carrier billed</th>"
        "<th style='padding:4px 8px;text-align:right'>Contract</th><th style='padding:4px 8px'></th></tr>"
        + "".join(rows_html) +
        "</table>"
        + (f"<p style='margin:10px 0 4px'><b>Evidence</b></p><ul style='margin:0;padding-left:18px'>{findings}</ul>" if findings else "")
        + f"<div style='margin-top:10px;padding:10px 12px;border-left:4px solid #2b59c3;background:#eef3fd'>"
        f"<b>AI recommendation: {e(rec_label)}</b><br>{e(r['recommendation_reason'])}<br>"
        "<small>You decide. You know the carrier relationship and any operational fault on your side; the system does not.</small></div>"
        "</div>"
    )


def verdict_form_html(r: dict) -> str:
    """Same verdict using only tags n8n forms allow (no style/class attributes).
    Colours come from FORM_CSS, which the n8n Form node injects as custom CSS."""
    e = html.escape
    fmc = r["fmc"]
    bad = r["verdict"] in ("overcharged", "invalid_fmc")
    head = f"<h2>{e(r['headline'])}</h2>" if bad else f"<h3>{e(r['headline'])}</h3>"
    if fmc["window_open"]:
        badge = f"Dispute window closes in {fmc['days_remaining']} days ({_fmt_day(fmc['dispute_deadline'])})"
    else:
        badge = f"Dispute window closed on {_fmt_day(fmc['dispute_deadline'])}"
    fmc_line = ("FMC 30-day billing rule: passed" if fmc["valid"]
                else f"FMC 30-day billing rule: FAILED, invoice issued {fmc['days_late']} days too late")
    wrap = {"chargeable": "b", "free": "u"}
    rows = []
    for row in r["day_table"]:
        tag = wrap.get(row["status"], "i")
        if row["wrongly_billed"]:
            mark = "<em>&#10007; Billed, not owed</em>"
        elif row["billed"]:
            mark = "&#10003; Billed, owed"
        elif row["status"] == "chargeable":
            mark = "Owed, not billed"
        else:
            mark = ""
        rows.append(
            f"<tr><td>{e(_fmt_day(row['date']))}</td><td><{tag}>{e(row['label'])}</{tag}><br>{e(row['reason'])}</td>"
            f"<td>{money(row['billed_charge']) if row['billed'] else '-'}</td>"
            f"<td>{money(row['correct_charge']) if row['correct_charge'] else '-'}</td><td>{mark}</td></tr>")
    findings = "".join(f"<li>{e(f['text'])}</li>" for f in r["findings"] if f["severity"] != "info")
    rec_label = {"dispute_full": "Dispute in full", "pay": "Pay invoice"}[r["recommendation"]]
    inv = r["invoice"]
    return (
        head
        + f"<p>Carrier billed <b>{r['billed_days']} days = {money(r['billed_amount'])}</b>. "
        f"Contract allows <b>{r['correct_days']} days = {money(r['correct_amount'])}</b>.</p>"
        f"<p><strong>{e(badge)}</strong> &nbsp; {e(fmc_line)}</p>"
        f"<p>{e(r['contract']['name'])} &middot; invoice {e(inv.get('invoice_number') or '-')} &middot; container "
        f"{e(inv['container_id'])} &middot; discharged {e(_fmt_day(r['gate_events']['discharge_date']))}, gate-out "
        f"{e(_fmt_day(r['gate_events']['gate_out_date']))} &middot; contract {e(r['contract']['contract_id'])}: "
        f"{r['contract']['free_days']} free working days, then {money(r['contract_rate'])}/day</p>"
        "<table><thead><tr><th>Day</th><th>Status (checked by code)</th><th>Billed</th><th>Contract</th><th></th></tr></thead>"
        "<tbody>" + "".join(rows) + "</tbody></table>"
        + (f"<h4>Evidence</h4><ul>{findings}</ul>" if findings else "")
        + f"<h4>AI recommendation: {e(rec_label)}</h4><p>{e(r['recommendation_reason'])}</p>"
        "<p><i>Your call. You know the carrier relationship and any fault on your side; the system does not.</i></p>"
    )


FORM_CSS = """:root{--container-width:720px}
div.html table{width:100%;border-collapse:collapse;font-size:13px;margin:8px 0 4px}
div.html th{text-align:left;border-bottom:2px solid #9ca3af;padding:5px 6px;color:#374151}
div.html td{padding:5px 6px;border-bottom:1px solid #e5e7eb;vertical-align:top;color:#374151}
div.html tbody tr:nth-child(even) td{background:#f9fafb}
div.html td b{color:#b45309}
div.html td u{color:#15803d;text-decoration:none;font-weight:600}
div.html td i{color:#6b7280;font-weight:600}
div.html td em{color:#b91c1c;font-weight:700;font-style:normal}
div.html h2{color:#b91c1c;font-size:26px;margin:4px 0 6px}
div.html h3{color:#15803d;font-size:26px;margin:4px 0 6px}
div.html h4{color:#1e3a8a;margin:16px 0 4px;font-size:15px}
div.html p strong{display:inline-block;background:#fff4dc;color:#8a5a00;padding:3px 10px;border-radius:999px}
div.html code{display:block;font-family:inherit;font-size:12px;background:#eef3fd;color:#1e3a8a;padding:6px 10px;border-radius:6px;margin-bottom:8px}
div.html pre{white-space:pre-wrap;font-family:inherit;background:#f8f8f8;padding:12px;border-radius:8px}
"""


# --------------------------------------------------------------------------
# Deterministic letter (fallback + fact sheet for the AI drafter)
# --------------------------------------------------------------------------

def letter_facts(r: dict, decision: str, disputed_amount: Any = None, reason: str = "") -> dict:
    """Everything the letter is allowed to say. The LLM may not add numbers or dates."""
    if decision not in ("dispute_full", "partial"):
        raise EngineError("INVALID_DECISION", "Letters are only drafted for 'dispute_full' or 'partial'.")
    full = r["disputable_amount"] if r["disputable_amount"] > 0 else max(r["overcharge"], 0.0)
    amt = parse_number(disputed_amount)
    notes = []
    if decision == "partial":
        if amt is None or amt <= 0:
            amt = round(full / 2, 2)
            notes.append(f"No partial amount given; defaulted to half of the disputable amount ({money(amt)}).")
        if amt > r["billed_amount"]:
            notes.append(f"Partial amount capped at the invoice total {money(r['billed_amount'])}.")
            amt = r["billed_amount"]
    else:
        amt = full
    amt = round(amt, 2)
    inv = r["invoice"]
    return {
        "decision": decision,
        "disputed_amount": amt,
        "disputed_amount_text": money(amt),
        "amount_to_pay": round(r["billed_amount"] - amt, 2),
        "amount_to_pay_text": money(r["billed_amount"] - amt),
        "carrier": r["contract"]["name"],
        "contract_id": r["contract"]["contract_id"],
        "invoice_number": inv.get("invoice_number") or "(no number)",
        "invoice_date": inv["invoice_date"],
        "container_id": inv["container_id"],
        "billed_text": f"{r['billed_days']} days, {money(r['billed_amount'])}",
        "correct_text": f"{r['correct_days']} days, {money(r['correct_amount'])}",
        "overcharge_text": money(max(r["overcharge"], 0.0)),
        "verdict": r["verdict"],
        "fmc_valid": r["fmc"]["valid"],
        "dispute_deadline": r["fmc"]["dispute_deadline"],
        "evidence": [f["text"] for f in r["findings"] if f["severity"] in ("high", "medium")
                     and f["code"] not in ("DISPUTE_WINDOW_CLOSING",)],
        "human_reason": (reason or "").strip(),
        "notes": notes,
        "allowed_amounts": sorted({money(x) for x in [amt, r["billed_amount"] - amt, r["billed_amount"],
                                                      r["correct_amount"], max(r["overcharge"], 0.0),
                                                      r["contract_rate"], r["billed_rate"]]}),
    }


def template_letter(f: dict, sender_name: str = "Sara Malik", company: str = "Northwind Imports Inc.") -> str:
    ev = "\n".join(f"  - {x}" for x in f["evidence"]) or "  - See attached day-by-day calculation."
    if f["decision"] == "partial":
        ask = (f"In the interest of our long-standing partnership, we are prepared to settle this invoice by paying "
               f"{f['amount_to_pay_text']} and request a credit of {f['disputed_amount_text']}.")
        tone_open = "We value our partnership with " + f["carrier"] + " and are writing about the invoice below."
    else:
        ask = (f"We therefore dispute {f['disputed_amount_text']} of this invoice and request a corrected invoice "
               f"for {f['amount_to_pay_text']}.")
        tone_open = "We are writing to formally dispute the demurrage charges on the invoice below."
    fmc = ("" if f["fmc_valid"] else
           "\nIn addition, this invoice was issued more than 30 days after charges were last incurred, which does not "
           "meet the billing requirements of the US Federal Maritime Commission (46 CFR Part 541).\n")
    return (
        f"Subject: Demurrage dispute: invoice {f['invoice_number']}, container {f['container_id']}\n\n"
        f"Dear {f['carrier']} Billing Team,\n\n"
        f"{tone_open}\n\n"
        f"Invoice: {f['invoice_number']} dated {f['invoice_date']}\n"
        f"Container: {f['container_id']}\n"
        f"Contract: {f['contract_id']}\n"
        f"Billed: {f['billed_text']}\n"
        f"Per contract: {f['correct_text']}\n\n"
        f"Our review of the contract terms, terminal gate records and port calendar found:\n{ev}\n{fmc}\n"
        f"{ask}\n\n"
        f"This dispute is submitted within the 30-day dispute period (deadline {f['dispute_deadline']}). "
        f"A day-by-day calculation is available on request.\n\n"
        f"Kind regards,\n{sender_name}\nLogistics Manager, {company}\n"
    )


_MONEY_RE = re.compile(r"(?:\$|USD\s?)\s?\d[\d,]*(?:\.\d{1,2})?")


def check_letter(letter: str, facts: dict) -> dict:
    """Guard: every money amount in an AI-drafted letter must come from the engine."""
    def key(s: str) -> str:
        digits = re.sub(r"[^\d.]", "", s).rstrip(".")
        try:
            return f"{float(digits):.2f}"
        except ValueError:
            return digits

    allowed = {key(a) for a in facts.get("allowed_amounts", [])}
    found = _MONEY_RE.findall(letter or "")
    bad = [m.strip() for m in found if key(m) not in allowed]
    return {"ok": not bad and bool((letter or "").strip()), "unknown_amounts": bad, "amounts_found": found}
