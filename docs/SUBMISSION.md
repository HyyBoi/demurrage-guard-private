# Submission PDF skeleton (one PDF per team, before 12:45 PM PKT)

Fill the blanks, export to PDF, open every link from a logged-out private window before submitting.

## 1. Team details
- Team name: ____
- Member 1: full name, email, Discord username
- Member 2: full name, email, Discord username
- WhatsApp contact: ____

## 2. About the project
- **Name:** DemurrageGuard
- **Pitch:** DemurrageGuard catches shipping-line overcharges in minutes: AI reads the invoice, code proves
  the math, and a human decides how to dispute.
- **Problem and audience:** Importers and freight forwarders receive demurrage & detention invoices that
  often bill excluded days (weekends, holidays, port closures, free time). Checking them by hand is slow,
  so teams pay, and US FMC rules give them only 30 days to dispute.
- **Where the human comes in:** (1) After the verdict, the logistics manager chooses pay, dispute in
  full or partial dispute, because the right answer depends on the carrier relationship and any fault on
  their own side, which no model can see. (2) The manager reviews, edits and approves the dispute letter
  before it is sent. If the AI cannot read the PDF, the human also corrects the extracted fields. Every
  decision, including overrides of the AI recommendation, is logged.
- **Built with:** n8n (form, AI extraction, AI agent, human approval steps), custom Python engine
  (FastAPI) exposed as REST and as an MCP server, Groq (openai/gpt-oss-120b), deployed on Alternate Clouds.

## 3. Links
- Live app (n8n form): https://n8n-j3bs-app.alternatefutures.ai/form/audit
- Landing page, sample verdicts, decision log, MCP server: https://alternate-glowing-serpent-8906-github-app.alternatefutures.ai
- GitHub: https://github.com/HyyBoi/demurrage-guard (workflow JSON in `n8n/`)
- Demo video: ____ (unlisted YouTube or Drive "anyone with the link")
- LinkedIn post: ____   Reshare: ____
- X post (optional): ____
- Sample invoices for judges: https://alternate-glowing-serpent-8906-github-app.alternatefutures.ai/samples/invoice_A_overcharged.pdf
  (also `_B_correct.pdf`, `_C_late_fmc.pdf`)
- Login: none needed for the form or the engine.

## 4. Proof screenshots
- Discord: both teammates visible in the Alternate Futures server
- Alternate Clouds dashboard: both services with deployment status (no keys visible)

## 5. Confirmations
- [ ] We wrote our LinkedIn post ourselves. Only grammar-only tools were used.
- [ ] Our project is deployed on Alternate Clouds.
- [ ] No API keys or personal or production passwords appear in our repository, video or screenshots.
- [ ] We have credited third-party code and templates (README > Credits).
- [ ] We will not change our code or deployment after 12:45 PM PKT on 17 October.
