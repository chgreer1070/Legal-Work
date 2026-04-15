"""
Generate sample contract PDFs with realistic FX clauses for demo.
"""

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

SAMPLE_CONTRACTS = [
    {
        "customer_name": "Acme Manufacturing S.A.",
        "contract_reference": "MSA-2025-0142",
        "filename": "acme_manufacturing_msa.pdf",
        "content": """MASTER SERVICE AGREEMENT

Between: Flex Ltd. ("Provider")
And: Acme Manufacturing S.A. ("Client")
Contract Reference: MSA-2025-0142
Effective Date: January 15, 2025

SECTION 7: PRICING AND CURRENCY ADJUSTMENTS

7.1 Base Pricing
All pricing under this Agreement is denominated in United States Dollars (USD) and calculated using the following base exchange rates established at contract inception:
- USD/BRL: 5.0500 (Brazilian Real)
- USD/MXN: 17.5000 (Mexican Peso)

7.2 Foreign Exchange Adjustment Clause
In the event that the prevailing market exchange rate for USD/BRL deviates from the base rate of 5.0500 by more than three percent (3%), either party may request a price adjustment to reflect the changed currency conditions. Such adjustments shall be reviewed on a monthly basis using the average daily rate published by the European Central Bank for the preceding calendar month.

7.3 Adjustment Method
Any adjustment triggered under Section 7.2 shall be applied as a full passthrough to the affected line items, effective thirty (30) calendar days following written notification to the Client. The Provider shall deliver such notification in writing, referencing this Section 7.2 and specifying the base rate, current rate, and calculated adjustment amount.

7.4 Mexican Peso Clause
For services rendered in Mexico, pricing is additionally subject to USD/MXN fluctuations. If the USD/MXN rate deviates from the base rate of 17.5000 by more than five percent (5%), pricing shall be adjusted on a quarterly basis using a shared adjustment method where each party absorbs fifty percent (50%) of the deviation impact. Written notice of sixty (60) days is required prior to any such adjustment.

SECTION 8: TERM AND TERMINATION
This Agreement shall remain in effect for a period of thirty-six (36) months from the Effective Date.""",
    },
    {
        "customer_name": "GlobalTech Electronics Co.",
        "contract_reference": "SOW-2025-0089",
        "filename": "globaltech_sow.pdf",
        "content": """STATEMENT OF WORK

Provider: Flex Ltd.
Client: GlobalTech Electronics Co.
SOW Reference: SOW-2025-0089
Date: March 1, 2025

ARTICLE 4: COMMERCIAL TERMS

4.1 Currency and Exchange Rate Provisions
This Statement of Work is priced in USD. The parties acknowledge that a significant portion of the manufacturing costs are incurred in Chinese Yuan (CNY). The base exchange rate for this SOW is USD/CNY: 7.2500.

4.2 FX Threshold and Adjustment
Should the USD/CNY exchange rate move beyond a four percent (4%) threshold from the base rate of 7.2500 in either direction, the Provider reserves the right to adjust unit pricing to reflect actual currency costs. Reviews shall be conducted quarterly, using the Bloomberg composite rate as reference.

4.3 Notification and Implementation
The Provider shall provide the Client with no less than forty-five (45) calendar days' written notice prior to implementing any FX-related price adjustment. Such notice shall include:
(a) The specific contract clause being invoked
(b) The base rate and current prevailing rate
(c) The percentage deviation
(d) The proposed adjustment to unit pricing
(e) Supporting documentation from the reference rate source

The adjustment method shall be capped at seventy-five percent (75%) of the total deviation impact, with the Provider absorbing the remaining twenty-five percent (25%).

ARTICLE 5: VOLUME COMMITMENTS
Client commits to minimum annual volumes as specified in Exhibit A.""",
    },
    {
        "customer_name": "Sunrise Consumer Products",
        "contract_reference": "MFG-2024-0215",
        "filename": "sunrise_manufacturing.pdf",
        "content": """MANUFACTURING AGREEMENT

Between: Flex Ltd. (the "Manufacturer")
And: Sunrise Consumer Products (the "Company")
Agreement Number: MFG-2024-0215
Effective: September 1, 2024

SCHEDULE C: PRICING MECHANISM

C.1 Reference Currencies
Manufacturing operations for this Agreement span multiple geographies. The following base exchange rates are established for pricing purposes:
- USD/BRL: 4.9800 (for Sorocaba facility operations)

C.2 Exchange Rate Protection Mechanism
To manage foreign exchange risk, the parties agree to the following mechanism:

(a) Threshold: If the USD/BRL exchange rate deviates by more than five percent (5.0%) from the base rate specified in C.1, a price review shall be triggered.

(b) Review Period: Exchange rate reviews shall be conducted on a semi-annual basis, using the arithmetic mean of daily closing rates as published by the Central Bank of Brazil (PTAX) for the relevant six-month period.

(c) Adjustment: Adjustments shall be applied as full passthrough of the deviation beyond the 5% threshold band. For example, if the rate deviates by 7%, only the 2% beyond the threshold is passed through.

(d) Notice: The Manufacturer shall provide ninety (90) calendar days' advance written notice before implementing any price adjustment under this clause, allowing the Company adequate time to adjust its downstream pricing.

C.3 Rate Lock Option
The Company may elect to lock the exchange rate for any six-month period by entering into a separate hedging arrangement, details of which shall be governed by Schedule D.""",
    },
]


def generate_sample_pdfs(output_dir: str = "fx_uploads") -> list[dict]:
    """Generate sample contract PDFs and return contract metadata."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ContractTitle",
        parent=styles["Title"],
        fontSize=14,
        spaceAfter=12,
    )
    body_style = ParagraphStyle(
        "ContractBody",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=8,
    )

    generated = []
    for contract in SAMPLE_CONTRACTS:
        filepath = out_path / contract["filename"]
        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=letter,
            rightMargin=inch,
            leftMargin=inch,
            topMargin=inch,
            bottomMargin=inch,
        )
        story = []
        for paragraph in contract["content"].split("\n\n"):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            escaped = paragraph.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            escaped = escaped.replace("\n", "<br/>")
            if paragraph.isupper() or paragraph.startswith("Between:") or paragraph.startswith("Provider:"):
                story.append(Paragraph(escaped, title_style))
            else:
                story.append(Paragraph(escaped, body_style))
            story.append(Spacer(1, 4))

        doc.build(story)
        generated.append({
            "customer_name": contract["customer_name"],
            "contract_reference": contract["contract_reference"],
            "filename": contract["filename"],
            "filepath": str(filepath),
            "content": contract["content"],
        })

    return generated
