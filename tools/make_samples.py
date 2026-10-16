"""Generate the three demo invoice PDFs in samples/. Fictional carrier and data.

    pip install reportlab
    python tools/make_samples.py
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

OUT = Path(__file__).resolve().parent.parent / "samples"

INVOICES = [
    {
        "file": "invoice_A_overcharged.pdf",
        "inv_no": "OCL-DD-2026-10-0147",
        "issued": "1 October 2026",
        "due": "31-OCT-2026",
        "bl": "OCLLAX2608812",
        "vessel": "OCEANIC HORIZON / 214E",
        "container": "OLCU 482193-7",
        "size": "40' HC",
        "arrival": "01-SEP-2026",
        "period": ("06-SEP-2026", "14-SEP-2026"),
        "days": 9,
        "rate": 175.00,
        "free_note": "Free time: 5 days from discharge",
    },
    {
        "file": "invoice_B_correct.pdf",
        "inv_no": "OCL-DD-2026-10-0233",
        "issued": "5 October 2026",
        "due": "04-NOV-2026",
        "bl": "OCLLAX2609377",
        "vessel": "OCEANIC MERIDIAN / 031E",
        "container": "OLCU 553012-8",
        "size": "40' HC",
        "arrival": "14-SEP-2026",
        "period": ("21-SEP-2026", "25-SEP-2026"),
        "days": 5,
        "rate": 175.00,
        "free_note": "Free time: 5 working days per contract OCL-2026-SC-0417",
    },
    {
        "file": "invoice_C_late_fmc.pdf",
        "inv_no": "OCL-DD-2026-09-0612",
        "issued": "20 September 2026",
        "due": "20-OCT-2026",
        "bl": "OCLLAX2607104",
        "vessel": "OCEANIC HORIZON / 209E",
        "container": "OLCU 771940-2",
        "size": "20' DV",
        "arrival": "06-JUL-2026",
        "period": ("13-JUL-2026", "15-JUL-2026"),
        "days": 3,
        "rate": 175.00,
        "free_note": "Free time: 5 working days per contract OCL-2026-SC-0417",
    },
]


def draw(inv: dict) -> None:
    path = OUT / inv["file"]
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle(f"Oceanic Line invoice {inv['inv_no']}")
    w, h = A4
    navy = colors.HexColor("#14325c")

    # Letterhead
    c.setFillColor(navy)
    c.rect(0, h - 32 * mm, w, 32 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(18 * mm, h - 17 * mm, "OCEANIC LINE LTD.")
    c.setFont("Helvetica", 8.5)
    c.drawString(18 * mm, h - 23 * mm, "Container Shipping  |  Trans-Pacific  |  Asia - US West Coast")
    c.drawString(18 * mm, h - 27.5 * mm, "Billing Office: 1200 Harbor Plaza, Suite 400, Long Beach CA 90802, USA")
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(w - 18 * mm, h - 17 * mm, "DEMURRAGE / DETENTION")
    c.drawRightString(w - 18 * mm, h - 23 * mm, "INVOICE")

    c.setFillColor(colors.black)
    y = h - 44 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(18 * mm, y, "BILL TO")
    c.setFont("Helvetica", 9)
    for i, line in enumerate(["Northwind Imports Inc.", "Attn: Accounts Payable / Logistics",
                              "4410 Commerce Way", "Ontario, CA 91761, USA", "Cust. ref: NWI-AP-7781"]):
        c.drawString(18 * mm, y - (i + 1) * 4.6 * mm, line)

    meta = [("Invoice No.", inv["inv_no"]), ("Issue date", inv["issued"]), ("Payment due", inv["due"]),
            ("B/L No.", inv["bl"]), ("Vessel / Voy.", inv["vessel"]), ("Port", "USLAX - Los Angeles, CA"),
            ("Terms", "Net 30")]
    for i, (k, v) in enumerate(meta):
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(112 * mm, y - i * 4.6 * mm, k)
        c.setFont("Helvetica", 8.5)
        c.drawString(140 * mm, y - i * 4.6 * mm, v)

    # Container block
    y = h - 86 * mm
    c.setStrokeColor(colors.HexColor("#999999"))
    c.line(18 * mm, y + 4 * mm, w - 18 * mm, y + 4 * mm)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(18 * mm, y, "EQUIPMENT")
    c.setFont("Helvetica", 9)
    c.drawString(18 * mm, y - 5 * mm, f"Cntr: {inv['container']}   Type: {inv['size']}   "
                                      f"Discharged: {inv['arrival']}")
    c.drawString(18 * mm, y - 10 * mm, inv["free_note"] + ".  Charges computed per carrier tariff.")

    # Charges table
    y = h - 106 * mm
    c.setFillColor(colors.HexColor("#e8edf5"))
    c.rect(18 * mm, y - 2 * mm, w - 36 * mm, 7 * mm, fill=1, stroke=0)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 8.5)
    cols = [18, 62, 112, 132, 157]
    for x, t in zip(cols, ["Description", "Period", "Days", "Rate", "Amount"]):
        c.drawString((x + 2) * mm, y, t)
    total = inv["days"] * inv["rate"]
    y -= 8 * mm
    c.setFont("Helvetica", 8.5)
    c.drawString(20 * mm, y, "Import demurrage (terminal)")
    c.drawString(64 * mm, y, f"{inv['period'][0]} to {inv['period'][1]}")
    c.drawString(114 * mm, y, str(inv["days"]))
    c.drawString(134 * mm, y, f"USD {inv['rate']:,.2f}")
    c.drawString(159 * mm, y, f"USD {total:,.2f}")
    y -= 6 * mm
    c.setFillColor(colors.HexColor("#666666"))
    c.drawString(20 * mm, y, "Detention (merchant haulage)")
    c.drawString(64 * mm, y, "-")
    c.drawString(114 * mm, y, "0")
    c.drawString(134 * mm, y, "-")
    c.drawString(159 * mm, y, "USD 0.00")
    c.setFillColor(colors.black)
    y -= 4 * mm
    c.line(18 * mm, y, w - 18 * mm, y)

    for label, val, bold in [("Subtotal", total, False), ("Sales tax (0%)", 0.0, False),
                             ("TOTAL DUE", total, True)]:
        y -= 6 * mm
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 10 if bold else 8.5)
        c.drawString(125 * mm, y, label)
        c.drawRightString(w - 20 * mm, y, f"USD {val:,.2f}")

    # Small print / noise that a real invoice has
    y = 70 * mm
    c.setFont("Helvetica-Bold", 8)
    c.drawString(18 * mm, y, "REMIT TO")
    c.setFont("Helvetica", 8)
    for i, line in enumerate(["Oceanic Line Ltd. - Pacific Commerce Bank, San Pedro CA",
                              "ACH routing 000000000  |  Acct ending 0000  |  Ref: invoice number",
                              "Queries: dd-billing@oceanicline.example"]):
        c.drawString(18 * mm, y - (i + 1) * 4.2 * mm, line)
    c.setFont("Helvetica", 6.8)
    c.setFillColor(colors.HexColor("#555555"))
    small = [
        "Charges accrue per calendar day after expiry of free time in accordance with the carrier's tariff and",
        "the service contract between the parties. Disputes must be submitted in writing within 30 days of the",
        "invoice date. Late payment may result in suspension of credit and equipment release.",
        "This is a computer-generated document. FICTIONAL SAMPLE FOR DEMONSTRATION ONLY.",
    ]
    for i, line in enumerate(small):
        c.drawString(18 * mm, 40 * mm - i * 3.6 * mm, line)
    c.drawRightString(w - 18 * mm, 14 * mm, "Page 1 of 1")
    c.showPage()
    c.save()


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for inv in INVOICES:
        draw(inv)
        print("wrote", OUT / inv["file"])
