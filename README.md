# DemurrageGuard

**AI reads the invoice. Code proves the math. A human decides.**

Ocean carriers routinely overbill demurrage & detention (D&D): weekends, public holidays and port
closures that the contract excludes, free-time days, days after the container already left. Under the
US Federal Maritime Commission rules (46 CFR Part 541) a carrier must bill within 30 days of the last
charge, and the importer has 30 days to dispute. Checking each invoice by hand is slow, so most teams
just pay.

DemurrageGuard audits a carrier invoice PDF in about a minute and lets a logistics manager make the call.

**Live:** [landing page and sample verdicts](https://alternate-glowing-serpent-8906-github-app.alternatefutures.ai)
and [the audit form](https://n8n-j3bs-app.alternatefutures.ai/form/audit), both on Alternate Clouds.

Agentika 2.0 / NaSCon 2026. Theme: **Human + AI: Better Together**.

## How it works

```
Upload PDF (n8n form)
  -> AI reads the PDF into fields (Groq gpt-oss-120b, structured extraction) [AI]
  -> Engine audits it: contract + gate records + port calendar + FMC rules  [CODE]
       REST /audit  and  AI agent calling the same engine over MCP
       Guard node: both must agree; code is the source of truth
  -> Day-by-day verdict + AI recommendation
  -> Manager decides: Pay / Dispute in full / Partial dispute + reason       [HUMAN]
  -> AI drafts the dispute letter from engine facts only                    [AI]
  -> Letter guard: any amount the engine didn't produce -> verified template [CODE]
  -> Manager edits and approves; decision logged in the audit trail          [HUMAN]
```

| Who | Does what | Why |
|---|---|---|
| AI | Reads messy PDFs, recommends, drafts letters | Good at language, bad at arithmetic |
| Code | Every date and dollar | Must be exactly right and checkable |
| Human | Pay / dispute / partial, and letter sign-off | Knows the carrier relationship and any fault on their side |

**Hero example (invoice A):** container discharged Tue Sep 1, 2026; 5 free working days; gate-out Mon Sep 14;
$175/day. The carrier billed Sep 6 to 14 = 9 days = $1,575. The engine shows Sep 6, 12, 13 are weekends,
Sep 7 is Labor Day and Sep 8 is still free day 5. Only Sep 9, 10, 11 and 14 are chargeable: **$700.
Overcharged by $875.**

## Repo layout

```
engine/           FastAPI service: REST + MCP server (one process)
  logic.py        the deterministic audit (pure functions)
  app.py          /audit /letter /letter/check /decisions /health, MCP at /mcp
  ui.py           landing page, sample verdict pages, decision log
  data/           fictional contracts, terminal gate events, port holidays
  static/fonts/   self-hosted typefaces (also used by the n8n forms)
tests/            pytest suite (7 tests)
n8n/              demurrage-guard.json: the n8n workflow (import into n8n)
samples/          3 demo invoice PDFs (A overcharged, B correct, C late/FMC-invalid)
tools/            scripts that generate the sample PDFs and the n8n workflow JSON
docs/             deployment guide, demo script, submission checklist
Dockerfile        engine image, listens on PORT (8000)
```

## Run locally (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m pytest -q                       # 7 passed
uvicorn engine.app:app --port 8000        # open http://localhost:8000
```

## Engine API

| Endpoint | Purpose |
|---|---|
| `GET /` | Landing page, sample invoices, human decision log |
| `GET /demo/A` (B, C) | Verdict for a sample invoice, rendered by the engine |
| `GET /health` | Health check |
| `POST /audit` | `{"invoice": {...}, "as_of_date": "YYYY-MM-DD"}` -> full audit (always HTTP 200; check `ok`) |
| `POST /letter` | Facts the AI may use + deterministic letter |
| `POST /letter/check` | Guard for an AI-drafted letter |
| `POST /decisions`, `GET /decisions` | Human decision audit trail |
| `/mcp` | MCP server (streamable HTTP): `audit_invoice`, `get_contract`, `get_gate_events`, `get_calendar`, `check_fmc_window` |
| `GET /docs` | OpenAPI docs |

No environment variables are required. Optional: `FORM_URL` (where the "Audit an invoice" buttons point) and
`DEMO_AS_OF_DATE=2026-10-10` (pins "today" for demos).

## Deploy

See [docs/DEPLOY.md](docs/DEPLOY.md). Two services on Alternate Clouds: the engine (this repo's Dockerfile,
port 8000, built from GitHub) and n8n (the platform's n8n template).

## Data and disclaimer

Carriers, contracts, containers, invoices and people are fictional demo data. Rules are simplified for
demonstration and are not legal advice.

## Credits

- [FastAPI](https://fastapi.tiangolo.com/) and [Uvicorn](https://www.uvicorn.org/) (MIT / BSD)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) (`FastMCP`, MIT)
- [n8n](https://n8n.io/) (Sustainable Use License) and its LangChain AI nodes
- [Groq](https://groq.com/) API with the OpenAI gpt-oss-120b open-weight model
- [ReportLab](https://www.reportlab.com/) for generating the sample PDFs (BSD)
- Typefaces [Big Shoulders Display](https://fonts.google.com/specimen/Big+Shoulders+Display) and
  [Archivo](https://fonts.google.com/specimen/Archivo), SIL Open Font License, via [Fontsource](https://fontsource.org)
- Hosted on [Alternate Clouds](https://clouds.alternatefutures.ai)
- AI coding assistance: Claude (Anthropic) helped write code and docs; the team reviewed, tested and deployed it.
