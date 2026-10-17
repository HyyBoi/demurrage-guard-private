"""Pages served by the engine: landing page, sample verdicts, decision log.

Design: harbour ink + fog, Big Shoulders Display (container-marking signage) for display type,
Archivo for text. The one bold device is the day ledger: one cell per day, with port
hazard-tape stripes on days the carrier billed but the contract does not allow.
"""

from __future__ import annotations

import html
from datetime import date

from engine.logic import money

e = html.escape

CSS = """
@font-face{font-family:"Big Shoulders Display";font-weight:800;font-display:swap;src:url(/fonts/big-shoulders-display-latin-800-normal.woff2) format("woff2")}
@font-face{font-family:"Archivo";font-weight:400;font-display:swap;src:url(/fonts/archivo-latin-400-normal.woff2) format("woff2")}
@font-face{font-family:"Archivo";font-weight:500 600;font-display:swap;src:url(/fonts/archivo-latin-600-normal.woff2) format("woff2")}
@font-face{font-family:"Archivo";font-weight:700;font-display:swap;src:url(/fonts/archivo-latin-700-normal.woff2) format("woff2")}
:root{--ink:#0F2238;--ink-2:#2A3D55;--fog:#EDF1F4;--paper:#FFFFFF;--steel:#7C8FA3;--line:#D5DDE5;
--sea:#1F7A63;--sea-bg:#DDEFE8;--signal:#C8102E;--flag:#F2B705;
--display:"Big Shoulders Display",Impact,"Arial Narrow",sans-serif;--text:"Archivo",system-ui,sans-serif}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--fog);color:var(--ink);font:16px/1.55 var(--text);font-variant-numeric:tabular-nums}
a{color:var(--ink)}
:focus-visible{outline:3px solid var(--flag);outline-offset:2px}
.wrap{max-width:1080px;margin:0 auto;padding:0 24px}
header.top{background:var(--ink);color:#fff}
header.top .wrap{display:flex;align-items:center;justify-content:space-between;gap:16px;min-height:64px}
.mark{font:800 26px/1 var(--display);letter-spacing:.01em;color:#fff;text-decoration:none}
.mark span{color:var(--flag)}
.btn{display:inline-block;font:600 15px/1 var(--text);padding:13px 20px;border-radius:6px;text-decoration:none;border:2px solid var(--ink)}
.btn-primary{background:var(--flag);border-color:var(--flag);color:var(--ink)}
.btn-primary:hover{background:#ffca2c}
.btn-ghost{background:transparent;color:var(--ink)}
.btn-ghost:hover{background:#fff}
header.top .btn-primary{padding:10px 16px}
.hero{background:var(--paper);border-bottom:1px solid var(--line);padding:56px 0 48px}
.hero h1{font:800 clamp(40px,6.4vw,76px)/.98 var(--display);margin:0 0 18px;letter-spacing:-.005em}
.hero h1 span{display:block}
.hero p.lede{font-size:19px;max-width:62ch;margin:0 0 32px;color:var(--ink-2)}
.actions{display:flex;flex-wrap:wrap;gap:12px;margin-top:28px}
.ledger-wrap{overflow-x:auto;padding:4px 0 6px;margin:0 -4px}
.ledger{display:grid;grid-template-columns:repeat(var(--n),minmax(58px,1fr));gap:4px;min-width:calc(var(--n) * 62px);padding:0 4px}
.bracket{grid-row:1;border-top:3px solid var(--signal);position:relative;margin-bottom:10px;padding-top:6px;font-size:13px;font-weight:600;color:var(--signal);white-space:nowrap}
.bracket::before,.bracket::after{content:"";position:absolute;top:-3px;width:3px;height:10px;background:var(--signal)}
.bracket::before{left:0}.bracket::after{right:0}
.day{grid-row:2;border-radius:4px;padding:8px 6px 9px;min-height:84px;display:flex;flex-direction:column;justify-content:space-between;font-size:12px;line-height:1.25;background:var(--fog);color:var(--steel)}
.day b{font:800 22px/1 var(--display);display:block;color:inherit}
.day .wd{font-weight:600}
.day.free{background:var(--sea-bg);color:var(--sea)}
.day.owed{background:var(--ink);color:#fff}
.day.notowed{background:repeating-linear-gradient(-45deg,var(--flag) 0 9px,var(--ink) 9px 18px);color:var(--ink)}
.day.notowed .wd,.day.notowed b,.day.notowed .tag{background:var(--flag);padding:2px 5px;border-radius:3px;align-self:flex-start;font-weight:700}
.day.notowed b{padding:3px 5px 1px}
.day.gone{background:#E9E3F3;color:#5B3F8C}
.legend{display:flex;flex-wrap:wrap;gap:8px 20px;margin:14px 0 0;padding:0;list-style:none;font-size:14px;color:var(--ink-2)}
.legend li{display:flex;align-items:center;gap:8px}
.sw{width:18px;height:18px;border-radius:3px;display:inline-block;background:var(--fog);border:1px solid var(--line)}
.sw.free{background:var(--sea-bg);border-color:#b9ddd0}.sw.owed{background:var(--ink);border-color:var(--ink)}
.sw.notowed{background:repeating-linear-gradient(-45deg,var(--flag) 0 4px,var(--ink) 4px 8px);border-color:var(--ink)}
.caption{font-size:14px;color:var(--steel);margin:10px 0 0}
.swipe{display:none;font-size:14px;color:var(--steel);margin:4px 0 0}
section.band{padding:56px 0;border-bottom:1px solid var(--line)}
section.band h2{font:800 40px/1.05 var(--display);margin:0 0 24px}
.steps{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(3,1fr);gap:32px;counter-reset:s}
.steps li{counter-increment:s;border-top:3px solid var(--ink);padding-top:14px}
.steps li::before{content:counter(s);font:800 44px/1 var(--display);display:block;margin-bottom:8px}
.steps h3{font:700 19px/1.3 var(--text);margin:0 0 6px}
.steps p{margin:0;color:var(--ink-2);max-width:40ch}
.who{display:inline-block;font-size:13px;font-weight:600;padding:2px 8px;border-radius:999px;margin-bottom:8px}
.who.ai{background:#E3E9F7;color:#24408E}.who.code{background:var(--ink);color:#fff}.who.you{background:var(--flag);color:var(--ink)}
table.t{width:100%;border-collapse:collapse;background:var(--paper);border:1px solid var(--line);border-radius:8px;overflow:hidden}
table.t th{text-align:left;font-size:13px;font-weight:600;color:var(--steel);padding:12px 14px;border-bottom:1px solid var(--line)}
table.t td{padding:13px 14px;border-bottom:1px solid var(--line);vertical-align:top}
table.t tr:last-child td{border-bottom:0}
.v-bad{color:var(--signal);font-weight:700}.v-ok{color:var(--sea);font-weight:700}
.links a{margin-right:14px;white-space:nowrap}
.scroll{overflow-x:auto}
.counts{font-size:19px;margin:0 0 20px;max-width:70ch}
.counts strong{font:800 28px/1 var(--display)}
.empty{background:var(--paper);border:1px dashed var(--steel);border-radius:8px;padding:22px;color:var(--ink-2)}
footer{padding:36px 0 56px;color:var(--ink-2);font-size:14px}
footer p{max-width:80ch;margin:0 0 8px}
code{font-size:.92em;background:#E2E8EE;padding:1px 5px;border-radius:4px}
.verdict-head{font:800 clamp(36px,5vw,60px)/1 var(--display);margin:0 0 10px}
.verdict-head.bad{color:var(--signal)}.verdict-head.ok{color:var(--sea)}
.facts{font-size:18px;margin:0 0 16px}
.flags{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 28px}
.flag{font-size:14px;font-weight:600;padding:6px 12px;border-radius:999px;background:var(--fog);border:1px solid var(--line)}
.flag.warn{background:#FFF3C9;border-color:#EAD27A}.flag.fail{background:#FBE3E6;border-color:#EFB3BC;color:var(--signal)}
.flag.pass{background:var(--sea-bg);border-color:#b9ddd0;color:var(--sea)}
.evidence{margin:0;padding-left:20px;max-width:75ch}
.evidence li{margin-bottom:6px}
.rec{margin-top:28px;border-left:4px solid var(--ink);background:var(--paper);padding:16px 20px;max-width:75ch}
.rec h3{margin:0 0 6px;font-size:18px}
.rec p{margin:0 0 6px}
.muted{color:var(--steel)}
.st-free{color:var(--sea);font-weight:600}.st-owed{color:var(--ink);font-weight:700}
.st-ex{color:var(--steel);font-weight:600}.st-gone{color:#5B3F8C;font-weight:600}
.no{color:var(--signal);font-weight:700}
@media (max-width:760px){
 .wrap{padding:0 16px}.hero{padding:36px 0 32px}.hero p.lede{font-size:17px}
 .steps{grid-template-columns:1fr;gap:24px}section.band{padding:40px 0}section.band h2{font-size:32px}
 header.top .btn-primary{display:none}.swipe{display:block}
}
@media (prefers-reduced-motion:no-preference){
 .ledger.animate .day{opacity:0;transform:translateY(6px);animation:dayin .35s ease-out forwards;animation-delay:calc(var(--i) * 55ms)}
 .ledger.animate .bracket{opacity:0;animation:dayin .4s ease-out forwards;animation-delay:calc(var(--n) * 55ms + 150ms)}
 @keyframes dayin{to{opacity:1;transform:none}}
}
"""


def page(title: str, body: str, form_url: str) -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<link rel="preload" href="/fonts/big-shoulders-display-latin-800-normal.woff2" as="font" type="font/woff2" crossorigin>
<style>{CSS}</style></head><body>
<header class="top"><div class="wrap"><a class="mark" href="/">Demurrage<span>Guard</span></a>
<a class="btn btn-primary" href="{e(form_url)}">Audit an invoice</a></div></header>
<main>{body}</main>
<footer><div class="wrap">
<p>For developers: the audit engine is open as REST (<code>POST /audit</code>, <a href="/docs">API docs</a>) and as an
MCP server at <code>/mcp</code> with the tools audit_invoice, get_contract, get_gate_events, get_calendar and check_fmc_window.</p>
<p>Runs on Alternate Clouds. Carriers, contracts, containers and invoices shown here are fictional demo data;
the rules are simplified and are not legal advice.</p></div></footer>
</body></html>"""


def _day_label(iso: str) -> tuple[str, str]:
    d = date.fromisoformat(iso)
    return d.strftime("%a"), f"{d.strftime('%b')} {d.day}"


def ledger(r: dict, animate: bool = False) -> str:
    """One cell per day from discharge to gate-out (and any billed days outside it)."""
    rows = r["day_table"]
    n = len(rows)
    billed_idx = [i for i, row in enumerate(rows) if row["billed"]]
    cells = []
    for i, row in enumerate(rows):
        wd, md = _day_label(row["date"])
        if row["wrongly_billed"]:
            cls = "notowed"
            tag = {"weekend": "Weekend", "holiday": row["reason"], "port_closure": "Port closed",
                   "free": f"Free day {row['free_day']}"}.get(row["status"], "Not at port")
        elif row["status"] == "chargeable":
            cls, tag = "owed", f"Owed {money(row['correct_charge'])}" if row["billed"] else "Owed, not billed"
        elif row["status"] == "free":
            cls, tag = "free", f"Free day {row['free_day']}"
        elif row["status"] in ("after_gate_out", "before_discharge"):
            cls, tag = "gone", "Not at port"
        else:
            cls, tag = "", {"weekend": "Weekend", "holiday": row["reason"], "port_closure": "Port closed"}[row["status"]]
        cells.append(f'<div class="day {cls}" style="--i:{i}"><span class="wd">{wd}</span>'
                     f'<b>{md.split()[1]}</b><span class="tag">{e(tag)}</span></div>')
    bracket = ""
    if billed_idx:
        a, b = billed_idx[0] + 1, billed_idx[-1] + 2
        bracket = (f'<div class="bracket" style="grid-column:{a}/{b}">Carrier billed {r["billed_days"]} days, '
                   f'{money(r["billed_amount"])}</div>')
    month = date.fromisoformat(rows[0]["date"]).strftime("%B %Y")
    return (f'<div class="ledger-wrap" role="img" aria-label="Day by day: carrier billed {r["billed_days"]} days, '
            f'contract allows {r["correct_days"]}"><div class="ledger{" animate" if animate else ""}" style="--n:{n}">'
            f'{bracket}{"".join(cells)}</div></div>'
            '<ul class="legend"><li><span class="sw free"></span>Free time</li>'
            '<li><span class="sw"></span>Weekend or holiday, excluded by contract</li>'
            '<li><span class="sw owed"></span>Chargeable, you owe it</li>'
            '<li><span class="sw notowed"></span>Billed, but not owed</li></ul>'
            f'<p class="caption">Container {e(r["invoice"]["container_id"])}, {e(r["contract"]["port_name"])}, '
            f'{month}. Computed live by the audit engine.</p>'
            '<p class="swipe">Swipe the days sideways to see the whole stay.</p>')


def verdict_block(r: dict) -> str:
    fmc = r["fmc"]
    bad = r["verdict"] in ("overcharged", "invalid_fmc")
    if fmc["window_open"]:
        window = (f'<span class="flag {"fail" if fmc["days_remaining"] <= 7 else "warn"}">'
                  f'{fmc["days_remaining"]} days left to dispute (until {_nice(fmc["dispute_deadline"])})</span>')
    else:
        window = f'<span class="flag">Dispute window closed {_nice(fmc["dispute_deadline"])}</span>'
    fmc_flag = ('<span class="flag pass">FMC 30-day billing rule passed</span>' if fmc["valid"] else
                f'<span class="flag fail">FMC 30-day billing rule failed: invoice {fmc["days_late"]} days late</span>')
    rows = []
    for row in r["day_table"]:
        wd, md = _day_label(row["date"])
        st = {"free": "st-free", "chargeable": "st-owed", "after_gate_out": "st-gone",
              "before_discharge": "st-gone"}.get(row["status"], "st-ex")
        mark = ('<span class="no">Billed, not owed</span>' if row["wrongly_billed"] else
                "Billed, owed" if row["billed"] else "Owed, not billed" if row["status"] == "chargeable" else "")
        rows.append(f'<tr><td>{wd} {md}</td><td><span class="{st}">{e(row["label"])}</span><br>'
                    f'<span class="muted">{e(row["reason"])}</span></td>'
                    f'<td>{money(row["billed_charge"]) if row["billed"] else ""}</td>'
                    f'<td>{money(row["correct_charge"]) if row["correct_charge"] else ""}</td><td>{mark}</td></tr>')
    ev = "".join(f"<li>{e(f['text'])}</li>" for f in r["findings"] if f["severity"] != "info")
    rec = {"dispute_full": "Dispute in full", "pay": "Pay the invoice"}[r["recommendation"]]
    c = r["contract"]
    return (f'<p class="verdict-head {"bad" if bad else "ok"}">{e(r["headline"])}</p>'
            f'<p class="facts">Billed {r["billed_days"]} days, {money(r["billed_amount"])}. '
            f'The contract allows {r["correct_days"]} days, {money(r["correct_amount"])}.</p>'
            f'<div class="flags">{window}{fmc_flag}</div>'
            + ledger(r, animate=True) +
            f'<p class="caption">Contract {e(c["contract_id"])}: {c["free_days"]} free working days from discharge, '
            f'then {money(c["rate_per_day"])} a day. Weekends, public holidays and port closures do not count.</p>'
            '<h2 style="font:800 30px/1.1 var(--display);margin:40px 0 14px">Every day, checked</h2>'
            '<div class="scroll"><table class="t"><thead><tr><th>Day</th><th>Status</th><th>Carrier billed</th>'
            '<th>Contract allows</th><th></th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>"
            + (f'<h3 style="margin:28px 0 8px;font-size:18px">What the carrier got wrong</h3><ul class="evidence">{ev}</ul>' if ev else "")
            + f'<div class="rec"><h3>AI recommendation: {rec}</h3><p>{e(r["recommendation_reason"])}</p>'
            '<p class="muted">The manager decides. They know the carrier relationship and any fault on their side.</p></div>')


def _nice(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.strftime('%b')} {d.day}"


def landing(hero: dict, samples: list[tuple[str, dict, dict]], decisions: list[dict], form_url: str) -> str:
    sample_rows = "".join(
        f'<tr><td><strong>{e(s["label"])}</strong><br><span class="muted">{e(s["about"])}</span></td>'
        f'<td class="{"v-bad" if r["verdict"] in ("overcharged", "invalid_fmc") else "v-ok"}">{e(r["headline"])}</td>'
        f'<td class="links"><a href="/demo/{k}">Open verdict</a><a href="/samples/{s["pdf"]}">Download PDF</a></td></tr>'
        for k, s, r in samples)
    if decisions:
        disputed = sum(float(d.get("disputed_amount") or 0) for d in decisions if d["human_decision"] != "pay")
        overrides = sum(1 for d in decisions if d["overrode_ai"])
        n = len(decisions)
        counts = (f'<p class="counts"><strong>{n}</strong> {"invoice" if n == 1 else "invoices"} decided, '
                  f'<strong>{overrides}</strong> {"time" if overrides == 1 else "times"} the manager overrode the AI, '
                  f'<strong>{money(disputed)}</strong> disputed.</p>')
        rows = "".join(
            f'<tr><td>{e(_when(d["at"]))}</td><td>{e(str(d.get("invoice_number") or "-"))}<br>'
            f'<span class="muted">{e(str(d.get("carrier") or ""))}</span></td>'
            f'<td>{e(_dec(d.get("ai_recommendation")))}</td><td><strong>{e(_dec(d["human_decision"]))}</strong>'
            f'{"<br><span class=no>Overrode the AI</span>" if d["overrode_ai"] else ""}</td>'
            f'<td>{e(str(d.get("reason") or ""))}</td></tr>' for d in decisions[:12])
        log = (counts + '<div class="scroll"><table class="t"><thead><tr><th>When (UTC)</th><th>Invoice</th>'
               '<th>AI recommended</th><th>Manager decided</th><th>Reason given</th></tr></thead>'
               f'<tbody>{rows}</tbody></table></div>')
    else:
        log = (f'<div class="empty">No decisions yet. <a href="{e(form_url)}">Audit an invoice</a> and the '
               'manager\'s choice will be recorded here, including every time they overrode the AI.</div>')
    body = f"""
<section class="hero"><div class="wrap">
<h1><span>The carrier billed {hero['billed_days']} days.</span> <span>The contract allows {hero['correct_days']}.</span></h1>
<p class="lede">DemurrageGuard checks a carrier's demurrage invoice against your contract, the terminal's gate records,
port holidays and the US FMC billing rules, and shows you what you actually owe. Then you decide: pay, dispute, or settle.</p>
{ledger(hero, animate=True)}
<div class="actions"><a class="btn btn-primary" href="{e(form_url)}">Audit an invoice</a>
<a class="btn btn-ghost" href="/demo/A">See this verdict in full</a></div>
</div></section>
<section class="band"><div class="wrap"><h2>How a check works</h2>
<ol class="steps">
<li><span class="who ai">AI</span><h3>Reads the invoice</h3><p>Upload the carrier's PDF. A language model pulls out the
carrier, container, dates and amounts. If it can't read something, you fill it in.</p></li>
<li><span class="who code">Code</span><h3>Checks every day</h3><p>A rules engine applies the contract's free time, skips
weekends, holidays and port closures, and checks the FMC 30-day rules. An AI agent repeats the check over MCP, and both
answers must match.</p></li>
<li><span class="who you">You</span><h3>Make the call</h3><p>Pay, dispute in full or settle part of it. The AI drafts
the letter, code checks every amount in it, and nothing is sent until you approve.</p></li>
</ol></div></section>
<section class="band"><div class="wrap"><h2>Try it with sample invoices</h2>
<p class="counts" style="font-size:17px">Download a PDF, then upload it on the audit page. Each verdict below is computed
live.</p>
<div class="scroll"><table class="t"><thead><tr><th>Invoice</th><th>Verdict</th><th></th></tr></thead>
<tbody>{sample_rows}</tbody></table></div></div></section>
<section class="band"><div class="wrap"><h2>Decisions so far</h2>{log}</div></section>
"""
    return page("DemurrageGuard: check demurrage invoices before you pay", body, form_url)


def demo_page(key: str, s: dict, r: dict, form_url: str) -> str:
    body = (f'<section class="hero"><div class="wrap">'
            f'<h1 style="font-size:clamp(30px,4vw,44px);max-width:none">{e(s["label"])} from {e(r["contract"]["name"])}</h1>'
            f'<p class="lede">{e(s["about"])}. Invoice {e(r["invoice"]["invoice_number"] or "")}, '
            f'container {e(r["invoice"]["container_id"])}, issued {_nice(r["invoice"]["invoice_date"])}.</p>'
            + verdict_block(r) +
            f'<div class="actions"><a class="btn btn-primary" href="{e(form_url)}">Audit it yourself</a>'
            f'<a class="btn btn-ghost" href="/samples/{s["pdf"]}">Download this invoice</a></div>'
            '</div></section>')
    return page(f"{s['label']}: {r['headline']}", body, form_url)


def error_page(r: dict, form_url: str) -> str:
    body = (f'<section class="hero"><div class="wrap"><h1>This invoice could not be checked</h1>'
            f'<p class="lede">{e(r.get("error", {}).get("message", "Unknown error"))}</p></div></section>')
    return page("Could not check invoice", body, form_url)


def _when(iso: str) -> str:
    return iso.replace("T", " ")[:16]


def _dec(v) -> str:
    return {"pay": "Pay", "dispute_full": "Dispute in full", "partial": "Partial dispute"}.get(str(v), str(v or "-"))
