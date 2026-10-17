# DemurrageGuard demo script

Say the lines in your own words. Times are targets, not limits.

## Before you hit record (5 min)

1. Open two browser tabs, zoom 110%:
   - Tab 1: https://alternate-glowing-serpent-8906-github-app.alternatefutures.ai
   - Tab 2: https://n8n-j3bs-app.alternatefutures.ai/form/audit
2. Put `invoice_A_overcharged.pdf`, `invoice_B_correct.pdf` and `invoice_C_late_fmc.pdf` on your Desktop.
3. Warm-up run, not recorded: upload **invoice B**, choose **Pay invoice**, reason "Billed correctly".
   This wakes the AI up so the recorded run is fast, and puts one entry in the decision log.
4. Reload Tab 1 and Tab 2. Turn off notifications (Windows: Focus assist).
5. Record with **Win+Alt+R** (stop with the same keys), or OBS.

## The 2–3 minute video

**0:00 · Tab 1, top of the landing page**
"Shipping lines charge importers a daily fee when a container stays at the port too long. The contract
says weekends and holidays don't count, but carriers bill them anyway. Checking every invoice takes hours,
so most companies just pay."
Point at the striped days: "Here the carrier billed nine days. The contract allows four."

**0:25 · Scroll to "How a check works"**
"AI reads the invoice. Code checks every day. And a human makes the call."

**0:35 · Tab 2, upload invoice A, click Check this invoice**
"I upload the carrier's PDF. The AI reads it, that's what AI is good at."
(Wait 20 to 40 seconds. Keep talking:) "Behind the scenes our engine runs on Alternate Clouds and checks the
contract, the terminal's gate records, the port holiday calendar and the US FMC billing rules."

**1:05 · Verdict page**
"Overcharged by $875." Point at the green line at the top: "An AI agent ran the same check through our MCP
server, and a guard confirms both answers match. If they ever disagree, the code wins. The AI never does the
maths." Scroll the table: "Sunday, Labor Day, a free day, a weekend. All billed, none owed."

**1:35 · Choose Partial dispute, type 400, reason, Confirm decision**
"The AI recommends disputing all $875. But I know Oceanic is a key partner and our trucker was late too.
The AI can't know that. So I settle: dispute $400." Reason to type:
`Key partner, and our trucker was also late on Sep 14.`

**2:00 · Letter page**
"The AI drafts the letter, and code checks that every dollar amount in it came from the engine. I can edit
it. Nothing goes out until I approve." Click **Approve letter**.

**2:20 · Tab 1, reload, scroll to "Decisions so far"**
"Every decision is logged, including when a human overrode the AI."

**2:35 · Tab 1, Invoice C, Open verdict**
"And an invoice sent more than 30 days late is invalid under US FMC rules, so the whole $525 can be
disputed." End.

## 6-minute finalist version

Same flow, slower, plus:
- **Problem (start):** "Return a rental car in 7 days or pay per day. They bill you 9 days late. You were 4,
  because their office was closed on a long weekend. Now imagine 200 cars."
- **After the verdict:** open Tab 1, Invoice A, Open verdict, to show the full day ledger.
- **Edge cases (after the letter):** upload invoice C live. Mention: unreadable PDF means the human fills in
  the fields; unknown carrier stops with a clear message; engine down means retry, then a manual path.
- **Close:** "n8n, Groq and our MCP engine, all on Alternate Clouds. AI reads, code proves, people decide."

## Likely judge questions

- **Why not let the AI calculate?** It gets dates wrong. Money has to be exact and auditable.
- **What if the AI misreads the PDF?** The person sees what it read and can fix it. The engine also flags
  inconsistencies: days versus period, rate versus contract, total versus days times rate.
- **Real data?** Contracts and gate records here are fictional. In production they come from the company's
  systems and terminal data; the rules engine stays the same.
- **Why a human at all?** Whether to dispute depends on the relationship and on your own fault. That is a
  business judgement, not a calculation.
