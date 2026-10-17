# Runbook

## What runs where

| Service | Where | Address |
|---|---|---|
| Engine (this repo) | Alternate Clouds, built from GitHub | https://alternate-glowing-serpent-8906-github-app.alternatefutures.ai |
| n8n (forms + workflow) | Alternate Clouds, n8n template | https://n8n-j3bs-app.alternatefutures.ai |
| Audit form | Inside n8n | https://n8n-j3bs-app.alternatefutures.ai/form/audit |

Both run in the cloud. Your laptop being off changes nothing. The laptop only matters when you push code.

## Starting a session (after a break, or after the laptop was off)

1. Open https://clouds.alternatefutures.ai, then your project.
2. Both services should say **Active**. If one says "Not running": Overview tab, Spend Controls
   **Pay as you go**, **Save**, then **Redeploy**, then wait for Active.
3. Open the engine address. You should see the landing page with the striped calendar.
4. Open the audit form address. You should see "Audit a demurrage invoice".
5. Warm-up: upload `samples/invoice_B_correct.pdf`, choose Pay. The first AI call after a break is slower.

The decision log lives in the engine's memory, so it starts empty after the engine restarts or redeploys.

## Changing the engine code

1. Edit, run `python -m pytest -q`, then `git add -A`, `git commit`, `git push`.
2. Dashboard: engine service, **Source** tab, **Rebuild**, wait for success, then **Deploy**.
3. The address stays the same. Spend control must stay **Pay as you go**.

Pushing only docs needs no rebuild.

## Changing the n8n workflow

The workflow file is generated: `python tools/build_workflow.py` writes `n8n/demurrage-guard.json`.

1. In n8n, unpublish and archive the current DemurrageGuard workflow (only one may use `/form/audit`).
2. **Create Workflow**, `...`, **Import from File**, choose `n8n/demurrage-guard.json`.
3. Check: the **Config** node's `engine_url` is the engine address above.
4. In **Groq (extract)**, **Groq (agent)** and **Groq (letter)**: pick the Groq credential, model
   `openai/gpt-oss-120b`.
5. **Ctrl+S** saves a draft only. Click **Publish**, wait 10 seconds, then open the form.

## n8n service variables

| Variable | Value |
|---|---|
| `N8N_HOST` | `0.0.0.0` |
| `N8N_PORT` | `5678` |
| `N8N_PROTOCOL` | `https` |
| `WEBHOOK_URL` | `https://n8n-j3bs-app.alternatefutures.ai` |
| `N8N_ENCRYPTION_KEY` | 32 random characters, set once. Never change it. |

The Groq API key is stored as an n8n credential, never in this repo.

## Optional engine variables

| Variable | Effect |
|---|---|
| `FORM_URL` | Where the "Audit an invoice" buttons point. Default: the audit form above |
| `DEMO_AS_OF_DATE` | Pins "today" for the dispute-window countdown, e.g. `2026-10-10` |

## When something breaks

| You see | Do this |
|---|---|
| Engine page 502 | Port must be 8000. Rebuild, then Deploy |
| A service says "Not running" | Pay as you go, Save, Redeploy |
| "Problem loading form" | Workflow not published, or published seconds ago. Publish, wait 10 seconds, reload |
| "No service found for this app subdomain" after uploading | The workflow points at an old engine address. Fix `engine_url` in Config and the MCP node URL, or re-import the file from this repo |
| Old look or old AI model after editing | You saved but didn't publish. Click Publish |
| The "check the invoice details" page every time | Groq key or model. n8n, Executions, open the newest run, click the red node |
| Verdict page never appears after upload | `WEBHOOK_URL` must be exactly the n8n address |
| Cross-check says "unavailable" | The MCP agent step failed; the verdict is still correct (it comes from the engine) |
| Anything else | Logs tab in the dashboard, then #support on the Alternate Futures Discord |
