# Demo script

Before you start: open the n8n form URL, the engine home page, and have `samples/` ready. Have the
recorded backup video open in another tab.

## 2–3 minute video (for shortlisting)

| Time | Show | Say (in your own words) |
|---|---|---|
| 0:00 | Engine home page | "Shipping lines overbill importers for container delays, and most companies just pay because checking takes hours. DemurrageGuard checks an invoice in about a minute." |
| 0:20 | Upload `invoice_A_overcharged.pdf` | "AI reads the messy PDF. That's the part AI is good at." |
| 0:40 | Verdict page | "Then our engine, plain code, checks the contract, the terminal gate records, the port calendar and the US FMC 30-day rules. AI never does the maths. Overcharged by $875: Sep 6, 12, 13 are weekends, Sep 7 is Labor Day, Sep 8 was still free time." |
| 1:10 | Cross-check badge | "An AI agent also runs the audit through our MCP server, and a guard checks both answers match. If they don't, code wins." |
| 1:25 | Pick **Partial dispute**, $400, reason | "The AI says dispute in full. But I know this carrier is a key partner and our trucker was late too. The AI can't know that. So I decide: partial." |
| 1:50 | Letter review page | "AI drafts the letter. Code checks every dollar amount in it came from the engine. I edit, I approve. Nothing goes out without me." |
| 2:15 | Engine home -> decision log | "Every human decision is logged, including when we overrode the AI." |
| 2:30 | `/demo/C` | "And an invoice sent too late is invalid under FMC rules, so the whole $525 can be disputed." |

## 6-minute finalist demo

1. **0:00 Problem (Usefulness, 20).** Car-rental analogy: "Return in 7 days or pay per day. They bill you
   9 days late. You were 4, because their office was closed on a long weekend. Now imagine 200 cars."
2. **0:45 Upload A (Automation, 15).** Show extraction happening in n8n.
3. **1:30 Verdict (Technical, 25).** Day table, $875, FMC badge. "AI reads, code computes." Point at the
   cross-check badge: MCP agent and REST engine agree.
4. **2:30 Override (Theme, 15).** AI recommends full dispute; human picks Partial and says why.
5. **3:30 Letter (UX, 10).** Draft, fact-check banner, edit, approve.
6. **4:30 Edge cases (Technical).** Upload C: FMC-invalid. Mention: unreadable PDF -> human fills the
   fields; unknown carrier -> clean error; engine down -> retry, then manual path.
7. **5:15 Architecture (Creativity, 15).** n8n + Groq + MCP engine, both on Alternate Clouds.
   "Global problem, US FMC rules, any importer or freight forwarder."

Likely judge questions:
- *Why not let the LLM calculate?* It gets dates wrong. Money must be exact and auditable.
- *What if the AI misreads the PDF?* The human sees what it read and can correct it; the engine also
  flags inconsistencies (days vs period, rate vs contract, total vs days x rate).
- *Real data?* Contract and gate data are fictional here; in production they'd come from the TMS and
  terminal APIs. The rules engine stays the same.
