"""Builds n8n/demurrage-guard.json (import it in n8n: Workflows > Import from file).

    python tools/build_workflow.py [https://<engine-service>-app.alternatefutures.ai]
"""

import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.logic import FORM_CSS  # noqa: E402

ENGINE_URL = (sys.argv[1] if len(sys.argv) > 1 else "https://alternate-glowing-serpent-8906-github-app.alternatefutures.ai").rstrip("/")
OUT = Path(__file__).resolve().parent.parent / "n8n" / "demurrage-guard.json"
GROQ_MODEL = "openai/gpt-oss-120b"  # llama-3.3-70b-versatile was retired by Groq on 2026-08-16

nodes: list[dict] = []
connections: dict = {}


def nid() -> str:
    return str(uuid.uuid4())


def node(name, type_, version, pos, params, **extra):
    n = {"parameters": params, "id": nid(), "name": name, "type": type_, "typeVersion": version,
         "position": list(pos)}
    n.update(extra)
    nodes.append(n)
    return name


def link(src, dst, out=0, kind="main", inp=0):
    c = connections.setdefault(src, {}).setdefault(kind, [])
    while len(c) <= out:
        c.append([])
    c[out].append({"node": dst, "type": kind, "index": inp})


def groq(name, pos):
    return node(name, "@n8n/n8n-nodes-langchain.lmChatGroq", 1, pos,
                {"model": GROQ_MODEL, "options": {"temperature": 0}})


CFG = "$('Config').first().json"
V = "$('Verdict Ready').first().json"
SAFE = {"onError": "continueRegularOutput"}
RETRY = {"retryOnFail": True, "maxTries": 2, "waitBetweenTries": 2000}

# ---------------------------------------------------------------- 1. intake
node("Upload Invoice", "n8n-nodes-base.formTrigger", 2.2, (0, 300), {
    "formTitle": "DemurrageGuard: audit a carrier invoice",
    "formDescription": ("Upload a demurrage / detention invoice (PDF). AI reads it, our engine checks it "
                        "against your contract, terminal gate records, the port calendar and US FMC billing "
                        "rules. Then you decide what to do."),
    "formFields": {"values": [
        {"fieldLabel": "Invoice PDF", "fieldType": "file", "multipleFiles": False,
         "acceptFileTypes": ".pdf", "requiredField": True},
    ]},
    "options": {"appendAttribution": False, "buttonLabel": "Audit invoice", "customCss": FORM_CSS},
}, webhookId=nid())

node("Read PDF Text", "n8n-nodes-base.extractFromFile", 1, (220, 300), {
    "operation": "pdf",
    "binaryPropertyName": "={{ Object.keys($binary || {})[0] || 'Invoice_PDF' }}",
    "options": {},
}, **SAFE)

node("Config", "n8n-nodes-base.set", 3.4, (440, 300), {
    "assignments": {"assignments": [
        {"id": nid(), "name": "engine_url", "value": ENGINE_URL, "type": "string"},
        {"id": nid(), "name": "as_of_date", "value": "", "type": "string"},
        {"id": nid(), "name": "pdf_text", "value": "={{ ($json.text || '').slice(0, 12000) }}", "type": "string"},
    ]},
    "includeOtherFields": False,
    "options": {},
}, notes="engine_url: your engine service URL. as_of_date: leave empty for today, or YYYY-MM-DD to pin the demo.")

# ---------------------------------------------------------------- 2. AI reads
EXTRACT_PROMPT = (
    "You extract fields from an ocean-freight carrier demurrage/detention invoice. "
    "Copy values exactly as printed; do not calculate or infer anything. "
    "Dates must be YYYY-MM-DD. container_id is 4 letters + 7 digits with spaces and dashes removed. "
    "charge_start and charge_end are the first and last day of the billed charge period. "
    "Numbers without currency symbols or commas. If a field is not on the invoice, omit it. Never guess."
)
node("AI: Read Invoice", "@n8n/n8n-nodes-langchain.informationExtractor", 1, (660, 300), {
    "text": "={{ $json.pdf_text }}",
    "attributes": {"attributes": [
        {"name": "carrier", "type": "string", "description": "Shipping line that issued the invoice"},
        {"name": "invoice_number", "type": "string", "description": "Invoice number"},
        {"name": "invoice_date", "type": "string", "description": "Issue date, YYYY-MM-DD"},
        {"name": "container_id", "type": "string", "description": "Container number, e.g. ABCU1234567"},
        {"name": "charge_start", "type": "string", "description": "First billed day, YYYY-MM-DD"},
        {"name": "charge_end", "type": "string", "description": "Last billed day, YYYY-MM-DD"},
        {"name": "rate_per_day", "type": "number", "description": "Daily rate charged"},
        {"name": "billed_days", "type": "number", "description": "Number of days billed"},
        {"name": "total_amount", "type": "number", "description": "Total amount due"},
        {"name": "currency", "type": "string", "description": "Currency code, e.g. USD"},
    ]},
    "options": {"systemPromptTemplate": EXTRACT_PROMPT},
}, **SAFE)
groq("Groq (extract)", (660, 520))
link("Groq (extract)", "AI: Read Invoice", kind="ai_languageModel")

# ---------------------------------------------------------------- 3. code computes
node("Engine: Audit", "n8n-nodes-base.httpRequest", 4.2, (880, 300), {
    "method": "POST",
    "url": f"={{{{ {CFG}.engine_url }}}}/audit",
    "sendBody": True,
    "specifyBody": "json",
    "jsonBody": f"={{{{ JSON.stringify({{ invoice: $json.output || {{}}, as_of_date: {CFG}.as_of_date }}) }}}}",
    "options": {"timeout": 20000},
}, **SAFE, **RETRY, notes="Deterministic truth. If the engine is down: retried once, then the human gets a fix/explain page.")

AGENT_SYSTEM = (
    "You are an invoice verification agent connected to the DemurrageGuard MCP server. "
    "Call the audit_invoice tool exactly once, passing the invoice fields you are given (dates as YYYY-MM-DD). "
    "Never do any arithmetic yourself. After the tool returns, reply with ONLY a JSON object copied from the tool "
    'result: {"verdict": ..., "correct_days": ..., "correct_amount": ..., "overcharge": ...}'
)
node("AI Agent: Verify via MCP", "@n8n/n8n-nodes-langchain.agent", 1.7, (1100, 300), {
    "promptType": "define",
    "text": ("=Audit this invoice with the audit_invoice tool.\nInvoice fields: "
             "{{ JSON.stringify($('AI: Read Invoice').first().json.output || {}) }}"
             f"{{{{ {CFG}.as_of_date ? '\\nas_of_date: ' + {CFG}.as_of_date : '' }}}}"),
    "options": {"systemMessage": AGENT_SYSTEM, "maxIterations": 4},
}, **SAFE)
groq("Groq (agent)", (1040, 520))
node("MCP: DemurrageGuard Engine", "@n8n/n8n-nodes-langchain.mcpClientTool", 1.1, (1200, 520), {
    "endpointUrl": f"{ENGINE_URL}/mcp",
    "serverTransport": "httpStreamable",
}, notes="Must point at <engine URL>/mcp (HTTP Streamable).")
link("Groq (agent)", "AI Agent: Verify via MCP", kind="ai_languageModel")
link("MCP: DemurrageGuard Engine", "AI Agent: Verify via MCP", kind="ai_tool")

GUARD_JS = r"""// Guard: the AI agent (via MCP) and the REST engine must agree. Code is the source of truth.
const rest = $('Engine: Audit').first().json;
const raw = (typeof $json.output === 'string') ? $json.output : '';
let guard = { status: 'unavailable',
  note: 'AI agent cross-check unavailable; showing the deterministic engine result.' };
if (rest.ok && raw) {
  try {
    const m = raw.match(/\{[\s\S]*\}/);
    const a = JSON.parse(m ? m[0] : raw);
    const same = Number(a.overcharge) === Number(rest.overcharge)
              && Number(a.correct_days) === Number(rest.correct_days);
    guard = same
      ? { status: 'match', note: `AI agent (via MCP) and engine agree: ${rest.correct_days} chargeable days, difference $${rest.overcharge}.` }
      : { status: 'mismatch', note: `AI agent said overcharge ${a.overcharge}, engine says ${rest.overcharge}. Using the engine: code is the source of truth.` };
  } catch (e) { /* keep 'unavailable' */ }
}
if (!rest.ok && !rest.error) {
  rest.error = { code: 'ENGINE_UNREACHABLE', message: 'The audit engine did not respond. Check the engine service, or enter the details manually.' };
}
const icon = { match: '\u2713', mismatch: '!', unavailable: 'i' }[guard.status];
const badge = `<code>${icon} Cross-check: ${guard.note}</code>`;
return [{ json: { ...rest, guard, form_html: rest.ok ? badge + rest.verdict_form_html : '' } }];
"""
node("Guard: Cross-check", "n8n-nodes-base.code", 2, (1320, 300), {"jsCode": GUARD_JS})

COND = lambda left: {  # noqa: E731  boolean "is true" condition for IF v2
    "conditions": {
        "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
        "conditions": [{"id": nid(), "leftValue": left, "rightValue": "",
                        "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
        "combinator": "and",
    },
    "looseTypeValidation": True,
    "options": {},
}
node("Verified?", "n8n-nodes-base.if", 2.2, (1540, 300), COND("={{ $json.ok === true }}"))

# ---------------------------------------------------------------- 3b. human fixes what AI could not read
FIX_HTML = ("={{ '<h3>We need your help with this invoice</h3><code>' + "
            "(($json.error && $json.error.message) || 'Unknown error').replace(/</g,'&lt;') + '</code>"
            "<p>The boxes below show what the AI read from the PDF. Correct anything wrong, fill anything missing, "
            "then re-run the audit. The engine does all the maths.</p>' }}")
AI_OUT = "($('AI: Read Invoice').first().json.output || {})"


def prefill(key):
    return f"={{{{ {AI_OUT}.{key} ?? '' }}}}"

node("Human: Fix Details", "n8n-nodes-base.form", 1, (1760, 520), {
    "formFields": {"values": [
        {"fieldType": "html", "elementName": "problem", "html": FIX_HTML},
        {"fieldLabel": "Carrier", "fieldType": "text", "defaultValue": prefill("carrier")},
        {"fieldLabel": "Invoice number", "fieldType": "text", "defaultValue": prefill("invoice_number")},
        {"fieldLabel": "Container number", "fieldType": "text", "defaultValue": prefill("container_id"),
         "placeholder": "e.g. OLCU4821937"},
        {"fieldLabel": "Invoice date", "fieldType": "date", "defaultValue": prefill("invoice_date")},
        {"fieldLabel": "Charge start", "fieldType": "date", "defaultValue": prefill("charge_start")},
        {"fieldLabel": "Charge end", "fieldType": "date", "defaultValue": prefill("charge_end")},
        {"fieldLabel": "Billed days", "fieldType": "number", "defaultValue": prefill("billed_days")},
        {"fieldLabel": "Rate per day", "fieldType": "number", "defaultValue": prefill("rate_per_day")},
        {"fieldLabel": "Total amount", "fieldType": "number", "defaultValue": prefill("total_amount")},
    ]},
    "options": {"formTitle": "Check the invoice details", "buttonLabel": "Re-run audit", "customCss": FORM_CSS},
}, webhookId=nid())

APPLY_JS = r"""// Merge the human's corrections over what the AI extracted.
const ai = $('AI: Read Invoice').first().json.output || {};
const f = $json;
const pick = (label) => (f[label] === undefined || f[label] === null || String(f[label]).trim() === '') ? undefined : f[label];
const fixed = { ...ai };
const map = { 'Carrier': 'carrier', 'Invoice number': 'invoice_number', 'Container number': 'container_id', 'Invoice date': 'invoice_date',
  'Charge start': 'charge_start', 'Charge end': 'charge_end', 'Billed days': 'billed_days',
  'Rate per day': 'rate_per_day', 'Total amount': 'total_amount' };
for (const [label, key] of Object.entries(map)) { const v = pick(label); if (v !== undefined) fixed[key] = v; }
return [{ json: { invoice: fixed, as_of_date: $('Config').first().json.as_of_date } }];
"""
node("Apply Fixes", "n8n-nodes-base.code", 2, (1980, 520), {"jsCode": APPLY_JS})
node("Engine: Re-audit", "n8n-nodes-base.httpRequest", 4.2, (2200, 520), {
    "method": "POST",
    "url": f"={{{{ {CFG}.engine_url }}}}/audit",
    "sendBody": True,
    "specifyBody": "json",
    "jsonBody": "={{ JSON.stringify($json) }}",
    "options": {"timeout": 20000},
}, **SAFE, **RETRY)
node("Re-verified?", "n8n-nodes-base.if", 2.2, (2420, 520), COND("={{ $json.ok === true }}"))
node("Cannot Verify", "n8n-nodes-base.form", 1, (2640, 720), {
    "operation": "completion",
    "completionTitle": "Could not verify this invoice",
    "completionMessage": ("={{ (($json.error && $json.error.message) || 'The audit engine is unavailable.') + "
                          "' Do not pay yet: forward the invoice to the logistics team for a manual check.' }}"),
    "options": {"customCss": FORM_CSS},
}, webhookId=nid())

READY_JS = r"""// Single place the verified audit lives, whichever path it came from.
const r = $json;
if (!r.guard) {
  r.guard = { status: 'human_corrected', note: 'Audited after human corrections to the extracted fields.' };
  r.form_html = `<code>i ${r.guard.note}</code>` + r.verdict_form_html;
}
return [{ json: r }];
"""
node("Verdict Ready", "n8n-nodes-base.code", 2, (2640, 300), {"jsCode": READY_JS})

# ---------------------------------------------------------------- 4. HUMAN decides
node("Human: Decide", "n8n-nodes-base.form", 1, (2860, 300), {
    "formFields": {"values": [
        {"fieldType": "html", "elementName": "verdict", "html": "={{ $json.form_html }}"},
        {"fieldLabel": "Decision", "fieldType": "dropdown", "requiredField": True,
         "fieldOptions": {"values": [{"option": "Pay invoice"}, {"option": "Dispute in full"},
                                     {"option": "Partial dispute"}]}},
        {"fieldLabel": "Partial amount (USD)", "fieldType": "number",
         "placeholder": "Only for a partial dispute: the amount you want credited"},
        {"fieldLabel": "Reason", "fieldType": "textarea", "requiredField": True,
         "placeholder": "Why? e.g. key partner, our trucker was also late on the last day"},
    ]},
    "options": {"formTitle": "Verdict: your call", "buttonLabel": "Submit decision", "customCss": FORM_CSS},
}, webhookId=nid(), notes="HUMAN GATE 1: the business decision the AI cannot make.")

SW_RULE = lambda value, key: {  # noqa: E731
    "conditions": {
        "options": {"caseSensitive": False, "leftValue": "", "typeValidation": "loose", "version": 2},
        "conditions": [{"id": nid(), "leftValue": "={{ $json.Decision }}", "rightValue": value,
                        "operator": {"type": "string", "operation": "equals"}}],
        "combinator": "and",
    },
    "renameOutput": True,
    "outputKey": key,
}
node("Route Decision", "n8n-nodes-base.switch", 3.2, (3080, 300), {
    "rules": {"values": [SW_RULE("Pay invoice", "Pay"), SW_RULE("Dispute in full", "Dispute in full"),
                         SW_RULE("Partial dispute", "Partial")]},
    "looseTypeValidation": True,
    "options": {},
})

LOG_BODY = (
    "={{ JSON.stringify({{ invoice_number: {V}.invoice.invoice_number, container_id: {V}.invoice.container_id, "
    "carrier: {V}.contract.name, ai_recommendation: {V}.recommendation, "
    "human_decision: $('Human: Decide').first().json.Decision, reason: $('Human: Decide').first().json.Reason, "
    "billed_amount: {V}.billed_amount, correct_amount: {V}.correct_amount, "
    "disputed_amount: {DISPUTED}, letter_source: {SOURCE} }}) }}"
)
node("Log: Pay", "n8n-nodes-base.httpRequest", 4.2, (3300, 120), {
    "method": "POST", "url": f"={{{{ {CFG}.engine_url }}}}/decisions", "sendBody": True, "specifyBody": "json",
    "jsonBody": LOG_BODY.replace("{V}", V).replace("{DISPUTED}", "0").replace("{SOURCE}", "null")
    .replace("{{ JSON", "{{ JSON").replace("({{", "({").replace("}})", "})"),
    "options": {"timeout": 10000},
}, **SAFE)
node("Payment Approved", "n8n-nodes-base.form", 1, (3520, 120), {
    "operation": "completion",
    "completionTitle": "Payment approved",
    "completionMessage": (f"={{{{ 'Invoice ' + ({V}.invoice.invoice_number || '') + ' approved for payment: $' + "
                          f"{V}.billed_amount + '. Your decision is logged in the audit trail.' }}}}"),
    "options": {"customCss": FORM_CSS},
}, webhookId=nid())

# ---------------------------------------------------------------- 5. AI drafts, code checks
node("Engine: Letter Facts", "n8n-nodes-base.httpRequest", 4.2, (3300, 400), {
    "method": "POST", "url": f"={{{{ {CFG}.engine_url }}}}/letter", "sendBody": True, "specifyBody": "json",
    "jsonBody": (f"={{{{ JSON.stringify({{ invoice: {V}.invoice, as_of_date: {CFG}.as_of_date, "
                 "decision: $json.Decision, disputed_amount: $json['Partial amount (USD)'], reason: $json.Reason }) }}"),
    "options": {"timeout": 20000},
}, **SAFE, **RETRY)

LETTER_PROMPT = (
    "=You write dispute letters for a logistics manager. Write a clear, professional email to the carrier's "
    "billing team.\n\nRULES:\n"
    "- Use ONLY the facts below. Do not add any number, amount or date that is not in FACTS.\n"
    "- decision 'partial' = warm, relationship-first tone; we pay part and ask for a credit of disputed_amount_text.\n"
    "- decision 'dispute_full' = firm, factual tone; we dispute disputed_amount_text.\n"
    "- If fmc_valid is false, state that the invoice was issued outside the FMC 30-day billing window.\n"
    "- Mention the manager's reason only if it helps the relationship; never admit fault beyond it.\n"
    "- Sign as Sara Malik, Logistics Manager, Northwind Imports Inc.\n"
    "- Output only the email: a Subject line, then the body. No commentary.\n\n"
    "FACTS:\n{{ JSON.stringify($json.facts, null, 2) }}\n\n"
    "Reference structure (you may improve wording, not facts):\n{{ $json.template_letter }}"
)
node("AI: Draft Letter", "@n8n/n8n-nodes-langchain.chainLlm", 1.5, (3520, 400), {
    "promptType": "define",
    "text": LETTER_PROMPT,
}, **SAFE)
groq("Groq (letter)", (3520, 620))
link("Groq (letter)", "AI: Draft Letter", kind="ai_languageModel")

node("Engine: Check Letter", "n8n-nodes-base.httpRequest", 4.2, (3740, 400), {
    "method": "POST", "url": f"={{{{ {CFG}.engine_url }}}}/letter/check", "sendBody": True, "specifyBody": "json",
    "jsonBody": (f"={{{{ JSON.stringify({{ invoice: {V}.invoice, as_of_date: {CFG}.as_of_date, "
                 "decision: $('Human: Decide').first().json.Decision, "
                 "disputed_amount: $('Human: Decide').first().json['Partial amount (USD)'], "
                 "reason: $('Human: Decide').first().json.Reason, letter: $json.text || '' }) }}"),
    "options": {"timeout": 20000},
}, **SAFE, **RETRY, notes="Letter guard: any money amount the engine did not produce -> fall back to the verified template.")

REVIEW_HTML = ("={{ '<code>' + ($json.source === 'ai_draft' ? '\\u2713 ' : '! ') + ($json.guard_note || '') + '</code>"
               "<p>Edit the letter below if you want. Nothing is sent until you approve it.</p>' }}")
node("Human: Review Letter", "n8n-nodes-base.form", 1, (3960, 400), {
    "formFields": {"values": [
        {"fieldType": "html", "elementName": "letter_check", "html": REVIEW_HTML},
        {"fieldLabel": "Final letter", "fieldType": "textarea", "requiredField": True,
         "defaultValue": "={{ $json.final_letter }}"},
    ]},
    "options": {"formTitle": "Review and sign off the dispute letter", "buttonLabel": "Approve letter",
                "customCss": FORM_CSS + "textarea{min-height:420px}"},
}, webhookId=nid(), notes="HUMAN GATE 2: nothing leaves without a human sign-off.")

FINAL_JS = r"""const chk = $('Engine: Check Letter').first().json;
const norm = (t) => String(t || '').replace(/\r/g, '').trim();
const approved = norm($json['Final letter']) || norm(chk.final_letter);
const edited = approved !== norm(chk.final_letter);
return [{ json: {
  final_letter: approved,
  letter_source: edited ? 'human_edited' : chk.source,
  disputed_amount: chk.facts ? chk.facts.disputed_amount : null,
} }];
"""
node("Finalize Letter", "n8n-nodes-base.code", 2, (4180, 400), {"jsCode": FINAL_JS})
node("Log: Dispute", "n8n-nodes-base.httpRequest", 4.2, (4400, 400), {
    "method": "POST", "url": f"={{{{ {CFG}.engine_url }}}}/decisions", "sendBody": True, "specifyBody": "json",
    "jsonBody": LOG_BODY.replace("{V}", V).replace("{DISPUTED}", "$json.disputed_amount")
    .replace("{SOURCE}", "$json.letter_source").replace("({{", "({").replace("}})", "})"),
    "options": {"timeout": 10000},
}, **SAFE)
node("Done", "n8n-nodes-base.form", 1, (4620, 400), {
    "operation": "completion",
    "completionTitle": "Dispute letter approved",
    "completionMessage": ("={{ 'Approved by you and logged in the audit trail. Final letter:\\n\\n' + "
                          "$('Finalize Letter').first().json.final_letter }}"),
    "options": {"customCss": FORM_CSS},
}, webhookId=nid())

# ---------------------------------------------------------------- wiring (main)
for a, b in [("Upload Invoice", "Read PDF Text"), ("Read PDF Text", "Config"), ("Config", "AI: Read Invoice"),
             ("AI: Read Invoice", "Engine: Audit"), ("Engine: Audit", "AI Agent: Verify via MCP"),
             ("AI Agent: Verify via MCP", "Guard: Cross-check"), ("Guard: Cross-check", "Verified?"),
             ("Human: Fix Details", "Apply Fixes"), ("Apply Fixes", "Engine: Re-audit"),
             ("Engine: Re-audit", "Re-verified?"), ("Verdict Ready", "Human: Decide"),
             ("Human: Decide", "Route Decision"), ("Log: Pay", "Payment Approved"),
             ("Engine: Letter Facts", "AI: Draft Letter"), ("AI: Draft Letter", "Engine: Check Letter"),
             ("Engine: Check Letter", "Human: Review Letter"), ("Human: Review Letter", "Finalize Letter"),
             ("Finalize Letter", "Log: Dispute"), ("Log: Dispute", "Done")]:
    link(a, b)
link("Verified?", "Verdict Ready", out=0)
link("Verified?", "Human: Fix Details", out=1)
link("Re-verified?", "Verdict Ready", out=0)
link("Re-verified?", "Cannot Verify", out=1)
link("Route Decision", "Log: Pay", out=0)
link("Route Decision", "Engine: Letter Facts", out=1)
link("Route Decision", "Engine: Letter Facts", out=2)

# Sticky notes for judges reading the canvas
nodes.append({"parameters": {"content": (
    "## DemurrageGuard\n**AI reads** (PDF extraction) -> **code computes** (engine via REST + MCP, "
    "guard cross-checks them) -> **human decides** (pay / dispute / partial) -> **AI drafts** letter -> "
    "**code checks** every amount -> **human approves**.\n\nAll numbers come from the engine, never the LLM."),
    "height": 200, "width": 520, "color": 4},
    "id": nid(), "name": "Sticky Note", "type": "n8n-nodes-base.stickyNote", "typeVersion": 1,
    "position": [0, 0]})

workflow = {
    "name": "DemurrageGuard",
    "nodes": nodes,
    "connections": connections,
    "pinData": {},
    "settings": {"executionOrder": "v1"},
    "active": False,
    "meta": {"templateCredsSetupCompleted": False},
    "tags": [],
}
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(workflow, indent=2), encoding="utf-8")
print("wrote", OUT, "nodes:", len(nodes), "engine:", ENGINE_URL)
