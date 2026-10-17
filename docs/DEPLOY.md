# Deploy DemurrageGuard: step by step

Two services on Alternate Clouds. Do them in this order.

| Service name (use exactly) | What | Port |
|---|---|---|
| `demurrage-engine` | This repo (Dockerfile) | 8000 |
| `demurrage-n8n` | n8n | 5678 (check Source tab) |

Public URLs follow `https://<service-name>-app.alternatefutures.ai`. If you use these exact names, the
workflow JSON already points at the right engine URL and you edit nothing.

Golden rule from the troubleshooting guide: **set variables -> Rebuild -> wait -> Deploy.**

---

## 0. Push the code to GitHub (Windows PowerShell)

```powershell
cd "C:\AHM\Agentika 2.0\demurrage-guard"
git status
```

If it says `not a git repository`, run once:

```powershell
git init
git remote add origin https://github.com/HyyBoi/demurrage-guard.git
git branch -M main
```

Then:

```powershell
git add .
git commit -m "DemurrageGuard engine, n8n workflow, samples"
git push -u origin main
```

Optional local check before pushing (needs Python 3.12):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m pytest -q
uvicorn engine.app:app --port 8000
```

Open http://localhost:8000 and http://localhost:8000/demo/A. Ctrl+C to stop.

---

## 1. Engine service (`demurrage-engine`)

1. clouds.alternatefutures.ai -> your project -> **Add Service** -> deploy from GitHub / Docker
   (the option that builds from a repo with a Dockerfile; if unsure, ask #support on Discord).
2. Repo: `HyyBoi/demurrage-guard`, branch `main`, Dockerfile at the repo root.
3. Name: **`demurrage-engine`**.
4. Source tab: **PORT = 8000**.
5. Variables: none needed. (Optional: `DEMO_AS_OF_DATE` = `2026-10-10` to pin the demo date.)
6. **Rebuild** -> wait for success -> **Deploy**.
7. Logs tab must show `Application startup complete`.
8. Open in a private window:
   - `https://alternate-glowing-serpent-8906-github-app.alternatefutures.ai/health` -> `{"status":"ok",...}`
   - `https://alternate-glowing-serpent-8906-github-app.alternatefutures.ai/demo/A` -> "Overcharged by $875"

502 Bad Gateway = PORT mismatch. Fix PORT to 8000, Rebuild, Deploy.

---

## 2. n8n service (`demurrage-n8n`)

1. Generate an encryption key in PowerShell and save it somewhere private (not in git):
   ```powershell
   [System.Guid]::NewGuid().ToString("N")
   ```
2. Add Service -> n8n (template if the dashboard offers one, otherwise Docker image `n8nio/n8n`).
3. Name: **`demurrage-n8n`**.
4. Variables:
   - `N8N_ENCRYPTION_KEY` = the 32-character key from step 1. **Never change it later.**
   - `WEBHOOK_URL` = `https://demurrage-n8n-app.alternatefutures.ai`
   - Optional, only if the logs complain about `X-Forwarded-For`: `N8N_PROXY_HOPS` = `1`
5. Source tab: PORT must match n8n's port (**5678** unless the template says otherwise).
6. **Rebuild** -> **Deploy**. Open `https://demurrage-n8n-app.alternatefutures.ai` and create the owner account
   (use a team email; this is your login, not for judges).

---

## 3. Import and wire the workflow (in the n8n editor)

1. **Groq key:** console.groq.com/keys -> Create API key. Copy it.
2. n8n -> **Credentials** -> Add credential -> **Groq** -> paste key -> Save.
3. **Workflows** -> **Create** -> top-right `...` menu -> **Import from File** -> choose
   `n8n/demurrage-guard.json` from the repo.
4. Open each of the 3 Groq nodes (`Groq (extract)`, `Groq (agent)`, `Groq (letter)`) -> pick the Groq
   credential. Model: `openai/gpt-oss-120b` (Groq retired the Llama 3.3 model in Aug 2026).
5. Only if your engine name is NOT `demurrage-engine`: edit the `Config` node (`engine_url`) and the
   `MCP: DemurrageGuard Engine` node (URL ending in `/mcp`).
6. Any node with a red warning triangle: open it, re-select the highlighted option, close it. (Node
   options differ slightly between n8n versions.)
7. **Save**, then **Publish / Activate** the workflow (toggle top-right).
8. Open the `Upload Invoice` node -> copy the **Production URL**. That is your app link for judges.

## 4. Test end to end

Open the production form URL in a private window and upload each sample from `samples/`:

| File | Expected |
|---|---|
| `invoice_A_overcharged.pdf` | "Overcharged by $875", 4 chargeable days, AI recommends Dispute in full |
| `invoice_B_correct.pdf` | "Invoice is correct: $875", AI recommends Pay |
| `invoice_C_late_fmc.pdf` | "Invoice invalid under FMC rules: $525 not payable" |

Then pick **Partial dispute**, amount `400`, a reason, approve the letter. Check
`https://alternate-glowing-serpent-8906-github-app.alternatefutures.ai/` -> your decision appears in the Human decision log.

## 5. If something breaks

| Symptom | Fix |
|---|---|
| Engine 502 | PORT = 8000 in Source tab, Rebuild, Deploy |
| Pushed code, nothing changed | Source tab -> Rebuild -> wait -> Deploy |
| n8n credentials won't save | `N8N_ENCRYPTION_KEY` set? Same key as before? |
| Form or webhook URL wrong | `WEBHOOK_URL` must be exactly `https://demurrage-n8n-app.alternatefutures.ai` |
| AI Agent / MCP node errors | The workflow still works: the guard falls back to the REST engine. Check the MCP URL ends in `/mcp` and transport is HTTP Streamable |
| Verdict page shows plain text, no colours | n8n strips some styling in forms. The content is still correct; `/demo/A` on the engine shows the styled version |
| Groq errors / rate limit | Wait a minute, or make a second key and switch the credential |
| Anything else | Logs tab first, then #support on Discord with repo link, error as a code block, exact steps |

**Cut line if n8n fights you:** delete the AI Agent + MCP + Groq (agent) nodes and connect
`Engine: Audit` straight to `Guard: Cross-check`. The guard will say "cross-check unavailable" and
everything else works. Keep `/mcp` deployed and say honestly in the demo that the MCP server is live.
