"""DemurrageGuard engine service.

One process, two doors to the same deterministic logic:
  * REST  : POST /audit, POST /letter, POST /letter/check, POST /decisions
  * MCP   : streamable HTTP at /mcp (tools: audit_invoice, get_contract, ...)

No secrets and no environment variables are required to start.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from engine import logic, ui

log = logging.getLogger("demurrage")
ROOT = Path(__file__).resolve().parent.parent
SAMPLES_DIR = ROOT / "samples"
DEMO_AS_OF = os.getenv("DEMO_AS_OF_DATE") or None  # optional: pin "today" for demos
# Public link to the n8n upload form (n8n Form Trigger uses the fixed path "audit").
FORM_URL = os.getenv("FORM_URL") or "https://n8n-j3bs-app.alternatefutures.ai/form/audit"

# --------------------------------------------------------------------------
# MCP server (same functions as REST)
# --------------------------------------------------------------------------

mcp = FastMCP(
    "DemurrageGuard",
    instructions=("Deterministic demurrage & detention invoice auditor. Always call audit_invoice "
                  "and report its numbers unchanged. Never do arithmetic yourself."),
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


def _compact(r: dict) -> dict:
    if not r.get("ok"):
        return r
    return {
        "ok": True,
        "verdict": r["verdict"],
        "headline": r["headline"],
        "recommendation": r["recommendation"],
        "billed_days": r["billed_days"],
        "billed_amount": r["billed_amount"],
        "correct_days": r["correct_days"],
        "correct_amount": r["correct_amount"],
        "overcharge": r["overcharge"],
        "disputable_amount": r["disputable_amount"],
        "chargeable_dates": r["chargeable_dates"],
        "fmc": {k: r["fmc"][k] for k in ("valid", "days_late", "dispute_deadline", "days_remaining")},
        "findings": [f["text"] for f in r["findings"]],
    }


@mcp.tool()
def audit_invoice(
    carrier: str,
    container_id: str,
    invoice_date: str,
    charge_start: str | None = None,
    charge_end: str | None = None,
    billed_days: float | None = None,
    rate_per_day: float | None = None,
    total_amount: float | None = None,
    invoice_number: str | None = None,
    currency: str | None = None,
    as_of_date: str | None = None,
) -> dict:
    """Audit a carrier demurrage/detention invoice against the contract, terminal gate records,
    port holiday calendar and the FMC 30-day rules. Dates as YYYY-MM-DD. Returns the verified
    verdict, correct chargeable days/amount, overcharge and evidence. Use these numbers as-is."""
    inv = dict(carrier=carrier, container_id=container_id, invoice_date=invoice_date,
               charge_start=charge_start, charge_end=charge_end, billed_days=billed_days,
               rate_per_day=rate_per_day, total_amount=total_amount,
               invoice_number=invoice_number, currency=currency)
    return _compact(logic.audit_invoice(inv, as_of_date or DEMO_AS_OF))


@mcp.tool()
def get_contract(carrier: str) -> dict:
    """Look up the demurrage contract terms (free days, excluded days, daily rate) for a carrier."""
    try:
        return {"ok": True, **logic.get_contract(carrier)}
    except logic.EngineError as e:
        return {"ok": False, "error": e.to_dict()}


@mcp.tool()
def get_gate_events(container_id: str) -> dict:
    """Terminal gate records for a container: discharge date and gate-out date."""
    try:
        return {"ok": True, **logic.get_gate_events(container_id)}
    except logic.EngineError as e:
        return {"ok": False, "error": e.to_dict()}


@mcp.tool()
def get_calendar(port: str, start: str, end: str) -> dict:
    """Port calendar between two dates (YYYY-MM-DD): weekends, public holidays, port closures."""
    try:
        return {"ok": True, "port": port, "days": logic.get_calendar(port, start, end)}
    except logic.EngineError as e:
        return {"ok": False, "error": e.to_dict()}


@mcp.tool()
def check_fmc_window(invoice_date: str, last_charge_date: str, as_of_date: str | None = None) -> dict:
    """FMC rule check: was the invoice issued within 30 days of the last charge, and how many
    days remain in the 30-day dispute window."""
    try:
        return {"ok": True, **logic.check_fmc_window(invoice_date, last_charge_date, as_of_date or DEMO_AS_OF)}
    except logic.EngineError as e:
        return {"ok": False, "error": e.to_dict()}


mcp_app = mcp.streamable_http_app()  # serves POST/GET /mcp


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI):
    async with mcp.session_manager.run():
        log.warning("DemurrageGuard engine ready: REST at /audit, MCP at /mcp")
        yield


# --------------------------------------------------------------------------
# REST API
# --------------------------------------------------------------------------

app = FastAPI(
    title="DemurrageGuard Engine",
    description="Deterministic audit engine for ocean-freight demurrage & detention invoices. "
                "AI reads the invoice, this code proves the math, a human decides.",
    version="1.0.0",
    lifespan=lifespan,
)

DECISIONS: deque = deque(maxlen=200)
DECISIONS_FILE = Path(os.getenv("DECISIONS_FILE", "/tmp/demurrage_decisions.jsonl"))


def _as_of(body: dict) -> str | None:
    v = body.get("as_of_date")
    return v if v not in (None, "", "null") else DEMO_AS_OF


def _invoice_from(body: dict) -> dict:
    inv = body.get("invoice", body)
    if isinstance(inv, str):  # n8n sometimes sends nested JSON as a string
        try:
            inv = json.loads(inv)
        except json.JSONDecodeError:
            inv = {}
    return inv if isinstance(inv, dict) else {}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "demurrage-engine", "mcp": "/mcp",
            "time": datetime.now(timezone.utc).isoformat()}


@app.post("/audit")
def audit(body: dict = Body(...)) -> dict:
    """Full audit. Always HTTP 200; check `ok`. Body: {"invoice": {...}, "as_of_date": "YYYY-MM-DD"}"""
    return logic.audit_invoice(_invoice_from(body), _as_of(body))


@app.post("/letter")
def letter(body: dict = Body(...)) -> dict:
    """Facts the AI may use + a deterministic fallback letter.
    Body: {"invoice": {...}, "decision": "dispute_full"|"partial", "disputed_amount": 400, "reason": "..."}"""
    r = logic.audit_invoice(_invoice_from(body), _as_of(body))
    if not r["ok"]:
        return r
    try:
        facts = logic.letter_facts(r, _decision(body.get("decision")), body.get("disputed_amount"),
                                   body.get("reason") or "")
    except logic.EngineError as e:
        return {"ok": False, "error": e.to_dict()}
    return {"ok": True, "facts": facts,
            "template_letter": logic.template_letter(facts, body.get("sender_name") or "Sara Malik")}


@app.post("/letter/check")
def letter_check(body: dict = Body(...)) -> dict:
    """Guard for the AI-drafted letter: if it contains any money amount the engine did not produce,
    fall back to the deterministic template. Body: same as /letter plus {"letter": "..."}"""
    base = letter(body)
    if not base.get("ok"):
        return base
    draft = (body.get("letter") or "").strip()
    g = logic.check_letter(draft, base["facts"])
    if not draft:
        source, note = "template_no_draft", "AI draft unavailable, so the verified template letter is shown."
    elif g["ok"]:
        source, note = "ai_draft", "AI draft passed the fact check: every amount in it comes from the engine."
    else:
        source = "template_fallback"
        note = ("The AI draft contained amounts the engine did not produce (" + ", ".join(g["unknown_amounts"])
                + "), so it was replaced with the verified template letter.")
    return {
        "ok": True,
        "guard_passed": source == "ai_draft",
        "unknown_amounts": g["unknown_amounts"],
        "final_letter": draft if source == "ai_draft" else base["template_letter"],
        "source": source,
        "guard_note": note,
        "facts": base["facts"],
    }


def _decision(v: Any) -> str:
    s = str(v or "").lower()
    if "partial" in s:
        return "partial"
    if "dispute" in s or "full" in s:
        return "dispute_full"
    if "pay" in s:
        return "pay"
    return s


@app.post("/decisions")
def record_decision(body: dict = Body(...)) -> dict:
    """Audit trail: who decided what, and whether they agreed with the AI."""
    rec = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "invoice_number": body.get("invoice_number"),
        "container_id": body.get("container_id"),
        "carrier": body.get("carrier"),
        "ai_recommendation": body.get("ai_recommendation"),
        "human_decision": _decision(body.get("human_decision")),
        "overrode_ai": _decision(body.get("human_decision")) != _decision(body.get("ai_recommendation")),
        "reason": body.get("reason"),
        "billed_amount": body.get("billed_amount"),
        "correct_amount": body.get("correct_amount"),
        "disputed_amount": body.get("disputed_amount"),
        "letter_source": body.get("letter_source"),
        "decided_by": body.get("decided_by") or "Logistics manager",
    }
    DECISIONS.appendleft(rec)
    try:
        with open(DECISIONS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except OSError:
        pass
    return {"ok": True, "record": rec, "count": len(DECISIONS)}


@app.get("/decisions")
def list_decisions() -> dict:
    return {"ok": True, "decisions": list(DECISIONS)}


# --------------------------------------------------------------------------
# Judge-friendly pages (work even if n8n is down)
# --------------------------------------------------------------------------

SAMPLE_INVOICES = {
    "A": {"label": "Invoice A", "about": "Overcharged: weekends, Labor Day and a free day billed", "pdf": "invoice_A_overcharged.pdf",
          "invoice": {"carrier": "Oceanic Line", "invoice_number": "OCL-DD-2026-10-0147",
                      "invoice_date": "2026-10-01", "container_id": "OLCU4821937",
                      "charge_start": "2026-09-06", "charge_end": "2026-09-14", "rate_per_day": 175,
                      "billed_days": 9, "total_amount": 1575, "currency": "USD"}},
    "B": {"label": "Invoice B", "about": "Billed correctly, so the right call is to pay", "pdf": "invoice_B_correct.pdf",
          "invoice": {"carrier": "Oceanic Line", "invoice_number": "OCL-DD-2026-10-0233",
                      "invoice_date": "2026-10-05", "container_id": "OLCU5530128",
                      "charge_start": "2026-09-21", "charge_end": "2026-09-25", "rate_per_day": 175,
                      "billed_days": 5, "total_amount": 875, "currency": "USD"}},
    "C": {"label": "Invoice C", "about": "Sent too late, so it is invalid under FMC rules", "pdf": "invoice_C_late_fmc.pdf",
          "invoice": {"carrier": "Oceanic Line", "invoice_number": "OCL-DD-2026-09-0612",
                      "invoice_date": "2026-09-20", "container_id": "OLCU7719402",
                      "charge_start": "2026-07-13", "charge_end": "2026-07-15", "rate_per_day": 175,
                      "billed_days": 3, "total_amount": 525, "currency": "USD"}},
}


def _sample(key: str, as_of: str | None = None) -> dict:
    return logic.audit_invoice(SAMPLE_INVOICES[key]["invoice"], as_of or DEMO_AS_OF)


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    samples = [(k, s, _sample(k)) for k, s in SAMPLE_INVOICES.items()]
    return ui.landing(samples[0][2], samples, list(DECISIONS), FORM_URL)


@app.get("/demo/{key}", response_class=HTMLResponse)
def demo(key: str, as_of_date: str | None = None) -> str:
    k = key.upper()
    if k not in SAMPLE_INVOICES:
        raise HTTPException(404, "Unknown sample. Use A, B or C.")
    r = _sample(k, as_of_date)
    return ui.demo_page(k, SAMPLE_INVOICES[k], r, FORM_URL) if r["ok"] else ui.error_page(r, FORM_URL)


FONTS_DIR = Path(__file__).resolve().parent / "static" / "fonts"


@app.get("/fonts/{name}")
def font(name: str):
    path = (FONTS_DIR / name).resolve()
    if path.parent != FONTS_DIR or not path.is_file() or path.suffix != ".woff2":
        raise HTTPException(404, "Not found")
    # CORS so the n8n forms (another origin) can use the same typefaces
    return FileResponse(path, media_type="font/woff2",
                        headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "public, max-age=86400"})


@app.get("/samples/{name}")
def sample_pdf(name: str):
    path = (SAMPLES_DIR / name).resolve()
    if path.parent != SAMPLES_DIR.resolve() or not path.is_file() or path.suffix != ".pdf":
        raise HTTPException(404, "Not found")
    return FileResponse(path, media_type="application/pdf", filename=name)


# MCP lives at /mcp. Mounted last so the REST routes above take priority.
app.mount("/", mcp_app)
