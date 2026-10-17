# Deploy and update

Live services on Alternate Clouds:

| What | URL |
|---|---|
| Engine (landing page, verdicts, decision log, REST, MCP) | https://alternate-glowing-serpent-8906-github-app.alternatefutures.ai |
| n8n (the audit form) | https://n8n-j3bs-app.alternatefutures.ai/form/audit |

## Update the engine after pushing code

1. Push to GitHub (`main`).
2. Dashboard: open the engine service, then **Source** tab, then **Rebuild**. Wait for the build to finish.
3. **Deploy** (or Redeploy). The URL stays the same.
4. Spend control must be **Pay as you go**. A budget cap stops the service.
5. Check `/health` and `/` in a private window.

## Update the n8n workflow

1. In n8n, open the old DemurrageGuard workflow, **unpublish** it, then archive or delete it.
2. **Create Workflow**, then `...` menu, **Import from File**, choose `n8n/demurrage-guard.json`.
3. The three Groq nodes use the credential named **Groq account**. If a node shows a warning, open it and pick that credential.
4. **Ctrl+S**, then **Publish**. The form is always at `<n8n URL>/form/audit` (set in the Upload Invoice node, Options, Form Path).

## n8n service variables

| Variable | Value |
|---|---|
| `N8N_HOST` | `0.0.0.0` |
| `N8N_PORT` | `5678` |
| `N8N_PROTOCOL` | `https` |
| `WEBHOOK_URL` | `https://n8n-j3bs-app.alternatefutures.ai` |
| `N8N_ENCRYPTION_KEY` | 32 random characters. Never change it. |

## If something breaks

| Symptom | Fix |
|---|---|
| Engine 502 | Port must be 8000. Rebuild, then Deploy |
| Service "Not running" | Spend control: Pay as you go, Save, then Redeploy |
| Form says "Problem loading form" | Workflow not published, or published seconds ago. Publish, wait 10 seconds, reload |
| Verdict page never appears after upload | `WEBHOOK_URL` is not exactly the n8n URL |
| "Check the invoice details" page every time | Groq key or model. n8n, Executions, open the red node |
| Anything else | Logs tab, then #support on Discord |
