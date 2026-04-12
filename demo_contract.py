"""
Demo EMS Manufacturing Agreement — a realistic 25-clause sample contract
for testing and demonstration of the ContractTwin 3D system.

This contract includes deliberately cross-referenced sections, realistic
financial terms, and intentional ambiguities for the parser to flag.
"""

DEMO_CONTRACT_TEXT = """
ELECTRONICS MANUFACTURING SERVICES AGREEMENT

This Electronics Manufacturing Services Agreement ("Agreement") is entered
into as of January 1, 2026 ("Effective Date") by and between TechVision
Corporation, a Delaware corporation ("Customer"), and Precision
Manufacturing Solutions Inc., a California corporation ("Manufacturer").

1. SCOPE OF WORK AND SERVICES

1.1 Manufacturer shall provide electronics manufacturing services
("Services") to Customer, including printed circuit board assembly (PCBA),
box-build assembly, functional testing, and packaging in accordance with
Customer's specifications, drawings, bills of material, and work
instructions provided from time to time. Manufacturer shall maintain
sufficient capacity to fulfill Customer's requirements as set forth in the
Forecast (defined in Section 3).

1.2 The specific products, quantities, pricing, and delivery requirements
shall be set forth in one or more Statements of Work ("SOW") executed by
both parties and attached hereto. In the event of a conflict between this
Agreement and any SOW, the terms of the SOW shall prevail with respect to
the specific products covered therein.

2. PRICING AND COST MODEL

2.1 Pricing for each Product shall be as set forth in the applicable SOW
pricing exhibit. Prices include direct material costs, manufacturing labor,
test labor, overhead allocation, and Manufacturer's agreed margin.

2.2 Manufacturer may request a price adjustment no more than once per
calendar quarter, with at least forty-five (45) days written notice,
supported by documented changes in material costs, labor rates, or
regulatory compliance costs. Customer shall not unreasonably withhold
consent to price adjustments that reflect verifiable cost increases.

2.3 Customer may request annual cost reduction targets. Manufacturer shall
use commercially reasonable efforts to achieve year-over-year cost
reductions of at least three percent (3%) through process improvements,
yield optimization, and supply chain efficiencies. Achieved savings shall
be shared equally between the parties.

3. FORECASTING AND DEMAND PLANNING

3.1 Customer shall provide Manufacturer with a twelve (12) month rolling
forecast of anticipated Product requirements, updated monthly by the fifth
(5th) business day of each calendar month. The first ninety (90) days of
each forecast shall constitute a binding commitment ("Binding Forecast").
The remaining nine (9) months shall be non-binding estimates provided for
planning purposes only.

3.2 Manufacturer may procure long-lead materials and components based on
the Binding Forecast and, with Customer's prior written authorization,
based on extended forecast periods for components with lead times exceeding
ninety (90) days. Customer acknowledges that material purchases made
pursuant to authorized forecasts create financial obligations as described
in Sections 6 and 9.

3.3 If actual orders fall below the Binding Forecast by more than twenty
percent (20%) in any calendar quarter, Customer shall compensate
Manufacturer for demonstrated capacity reservation costs and committed
material purchases, subject to Manufacturer's obligation to mitigate such
costs through reasonable reallocation efforts.

4. PURCHASE ORDERS

4.1 Customer shall issue firm purchase orders ("POs") at least thirty (30)
days prior to the requested delivery date, referencing the applicable SOW
and specifying Product part numbers, quantities, unit prices, requested
delivery dates, and shipping instructions. Manufacturer shall acknowledge
receipt of each PO within three (3) business days.

4.2 In the event of a conflict between the terms of a PO and this
Agreement, the terms of this Agreement shall prevail unless the PO
explicitly references a mutually agreed deviation.

4.3 Customer may cancel or reschedule a PO subject to the following: (a)
cancellations more than thirty (30) days before the scheduled ship date
shall incur no penalty beyond reimbursement of committed materials per
Section 6; (b) cancellations within thirty (30) days of the scheduled ship
date shall require payment for work-in-process plus committed materials;
(c) rescheduling requests beyond sixty (60) days from the original date
require Manufacturer's written consent.

5. MATERIALS MANAGEMENT AND PROCUREMENT

5.1 Manufacturer shall procure all raw materials and components in
accordance with Customer's approved vendor list ("AVL") and approved
manufacturer list ("AML"). Manufacturer shall not substitute materials or
suppliers without Customer's prior written approval.

5.2 Manufacturer shall maintain a material management system capable of
tracking lot codes, date codes, and country of origin for all components.
Manufacturer shall implement first-in-first-out ("FIFO") inventory
management practices.

5.3 Title to raw materials purchased by Manufacturer on behalf of Customer
shall pass to Customer upon payment. Risk of loss for all inventory held at
Manufacturer's facility shall remain with Manufacturer until delivery per
the applicable Incoterms (Section 12).

6. LONG-LEAD AND NON-CANCELLABLE MATERIALS

6.1 Certain components required for Product manufacturing have procurement
lead times exceeding ninety (90) days and are subject to non-cancellable,
non-returnable ("NCNR") purchase terms imposed by upstream suppliers.
Manufacturer shall maintain and provide to Customer a current list of all
NCNR components and their associated lead times.

6.2 Manufacturer shall obtain Customer's written authorization before
placing orders for NCNR materials in excess of the Binding Forecast
coverage. Customer shall be financially responsible for all NCNR materials
properly authorized, including in the event of forecast reduction, order
cancellation, or termination of this Agreement.

6.3 The aggregate value of outstanding NCNR commitments shall not exceed
five million dollars ($5,000,000) at any time without Customer's VP-level
written approval.

7. CONSIGNED INVENTORY

7.1 Customer may consign certain materials, components, or sub-assemblies
to Manufacturer for use in Product manufacturing ("Consigned Materials").
Title to Consigned Materials shall remain with Customer at all times.

7.2 Manufacturer shall segregate, identify, and account for all Consigned
Materials separately from Manufacturer-owned inventory. Manufacturer shall
bear the risk of loss for Consigned Materials while in its possession,
except for losses caused by defects in such materials or Customer
negligence.

8. SAFETY STOCK AND BUFFER INVENTORY

8.1 Manufacturer shall maintain safety stock levels as specified in the
applicable SOW, generally not less than two (2) weeks and not more than six
(6) weeks of forecasted demand for standard components. Safety stock levels
for long-lead items shall be determined by mutual agreement based on
supplier lead times and demand variability.

8.2 Costs associated with maintaining safety stock, including carrying
costs and warehousing, shall be included in the unit pricing unless
otherwise specified. Customer shall be responsible for excess safety stock
in the event of demand reduction per Section 9.

9. EXCESS AND OBSOLETE INVENTORY

9.1 Inventory shall be deemed "Excess" if it exceeds ninety (90) days of
forecasted demand based on the most recent Binding Forecast. Inventory
shall be deemed "Obsolete" if it can no longer be used in the manufacture
of current Products due to engineering changes, product discontinuation, or
specification revisions.

9.2 Manufacturer shall notify Customer within fifteen (15) business days of
identifying Excess or Obsolete inventory. Customer shall, within thirty
(30) days of such notice: (a) provide updated forecasts demonstrating
planned consumption; (b) authorize return of materials to suppliers where
possible, at Customer's expense; or (c) purchase such inventory at
Manufacturer's fully burdened cost plus a fifteen percent (15%) handling
charge.

9.3 If Customer fails to respond within the thirty (30) day period,
Manufacturer may invoice Customer for the Excess or Obsolete inventory at
the rate specified in Section 9.2(c). Customer's failure to pay such
invoice within sixty (60) days shall constitute a material breach.

10. ENGINEERING CHANGES

10.1 Customer may issue engineering change orders ("ECOs") at any time by
written notice to Manufacturer. Manufacturer shall evaluate each ECO within
ten (10) business days and provide Customer with an impact assessment
covering: (a) cost impact; (b) delivery schedule impact; (c) material
disposition requirements; and (d) any tooling or process changes required.

10.2 Customer shall bear all costs associated with implementing approved
ECOs, including but not limited to: obsolete material resulting from the
change, tooling modifications, process requalification, and any required
first article inspections. Pricing shall be adjusted per Section 2.2 to
reflect ongoing cost changes resulting from the ECO.

10.3 Manufacturer shall not implement any ECO until receiving written
approval from Customer's authorized representative. Emergency ECOs
affecting product safety or regulatory compliance may be implemented with
verbal authorization, followed by written confirmation within forty-eight
(48) hours.

11. QUALITY STANDARDS AND INSPECTION

11.1 Manufacturer shall maintain ISO 9001:2015 certification (or
equivalent) and shall comply with IPC-A-610 Class 2 workmanship standards
(or Class 3 where specified in the SOW) throughout the term of this
Agreement. Manufacturer shall notify Customer within five (5) business days
of any lapse, suspension, or material finding related to its quality
certifications.

11.2 Customer shall have the right to inspect Manufacturer's facility,
processes, and quality records upon five (5) business days' prior written
notice. Inspections shall not unreasonably interfere with Manufacturer's
operations.

11.3 Manufacturer shall implement incoming material inspection, in-process
inspection, and final quality acceptance testing as defined in the
applicable SOW test procedures. Products shall not be shipped until they
have passed all required quality gates.

12. DELIVERY AND LOGISTICS

12.1 Delivery terms shall be FCA Manufacturer's facility (Incoterms 2020)
unless otherwise specified in the SOW. Risk of loss and title shall
transfer to Customer upon delivery to the carrier.

12.2 Manufacturer shall maintain an on-time delivery rate of at least
ninety-five percent (95%) measured monthly. Manufacturer shall notify
Customer within twenty-four (24) hours of any anticipated delivery delay
and shall provide a recovery plan within three (3) business days.

12.3 Customer shall be responsible for all freight, insurance, and customs
costs from Manufacturer's shipping dock unless otherwise agreed in writing.

13. PAYMENT TERMS

13.1 Manufacturer shall invoice Customer upon shipment of conforming
Products. Payment shall be due net sixty (60) days from date of invoice.
All amounts are in U.S. dollars.

13.2 Customer may withhold payment or assert setoff only for documented
quality defects, quantity discrepancies, or disputed charges, provided
Customer notifies Manufacturer of the dispute within fifteen (15) business
days of invoice receipt. Undisputed portions of invoices must be paid in
accordance with the payment schedule.

13.3 Late payments shall accrue interest at the lesser of one and one-half
percent (1.5%) per month or the maximum rate permitted by applicable law.
If Customer's payments are delinquent by more than forty-five (45) days,
Manufacturer may suspend production until the account is brought current.

14. WARRANTY

14.1 Manufacturer warrants that all Products manufactured under this
Agreement shall conform to Customer's approved specifications and shall be
free from defects in materials and workmanship for a period of eighteen
(18) months from the date of shipment or twelve (12) months from date of
installation by end customer, whichever occurs first ("Warranty Period").

14.2 Manufacturer's warranty obligations are limited to, at Manufacturer's
option: (a) repair of the defective Product; (b) replacement of the
defective Product; or (c) refund of the purchase price for the defective
Product. This warranty does not cover defects arising from Customer's
design, specifications, misuse, unauthorized modification, or normal wear
and tear.

14.3 Customer shall notify Manufacturer of warranty claims within thirty
(30) days of discovering the defect and shall provide reasonable access to
the Products for failure analysis. Manufacturer shall complete failure
analysis within fifteen (15) business days of receiving the returned
Product.

15. RMA AND FIELD RETURNS

15.1 Customer shall request a Return Material Authorization ("RMA") number
prior to returning any Product. Manufacturer shall issue RMA numbers within
two (2) business days of request. Products returned without a valid RMA
number may be refused.

15.2 Manufacturer shall complete failure analysis on returned Products
within fifteen (15) business days and provide a written failure analysis
report. For warranty returns, Manufacturer shall bear the cost of repair or
replacement. For non-warranty returns, Customer shall pay Manufacturer's
standard evaluation and repair fees.

16. INDEMNIFICATION

16.1 Manufacturer shall indemnify, defend, and hold harmless Customer and
its affiliates from and against any third-party claims, damages, losses,
and expenses (including reasonable attorneys' fees) arising from:
(a) Manufacturer's negligence or willful misconduct; (b) defects in
manufacturing workmanship (excluding defects arising from Customer's design
or specifications); (c) Manufacturer's violation of applicable law.

16.2 Customer shall indemnify, defend, and hold harmless Manufacturer from
and against third-party claims arising from: (a) Customer's product
designs, specifications, or instructions; (b) Customer's marketing,
labeling, or end-use of Products; (c) patent, trademark, or trade secret
infringement arising from Customer's designs.

16.3 The indemnifying party's obligations under this Section are conditioned
upon the indemnified party providing: (a) prompt written notice of the
claim; (b) reasonable cooperation; and (c) sole control of the defense and
settlement. See Section 17 for limitations on liability.

17. LIMITATION OF LIABILITY

17.1 EXCEPT FOR OBLIGATIONS UNDER SECTION 16 (INDEMNIFICATION) AND BREACHES
OF SECTION 19 (CONFIDENTIALITY), NEITHER PARTY'S AGGREGATE LIABILITY UNDER
THIS AGREEMENT SHALL EXCEED THE TOTAL AMOUNTS PAID OR PAYABLE BY CUSTOMER
TO MANUFACTURER DURING THE TWELVE (12) MONTHS PRECEDING THE EVENT GIVING
RISE TO THE CLAIM.

17.2 IN NO EVENT SHALL EITHER PARTY BE LIABLE FOR ANY INDIRECT, INCIDENTAL,
SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, INCLUDING BUT NOT LIMITED TO
LOST PROFITS, LOST REVENUE, OR COST OF SUBSTITUTE PRODUCTS, REGARDLESS OF
WHETHER SUCH PARTY HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.

18. INSURANCE

18.1 Manufacturer shall maintain the following insurance coverage throughout
the term: (a) commercial general liability of at least five million dollars
($5,000,000) per occurrence; (b) product liability of at least ten million
dollars ($10,000,000) aggregate; (c) property insurance covering Customer's
Consigned Materials; (d) workers' compensation as required by law.

18.2 Manufacturer shall provide certificates of insurance to Customer
annually and upon request, naming Customer as additional insured on
commercial general liability and product liability policies.

19. CONFIDENTIALITY AND EXPORT CONTROL

19.1 Each party shall maintain the confidentiality of the other party's
proprietary and confidential information and shall not disclose such
information to third parties without prior written consent. Confidentiality
obligations shall survive termination of this Agreement for a period of
five (5) years.

19.2 Manufacturer shall comply with all applicable export control laws and
regulations, including ITAR and EAR where applicable. Manufacturer shall
not export, re-export, or transfer any controlled items, technical data, or
software without appropriate government authorization.

20. INTELLECTUAL PROPERTY AND TOOLING

20.1 Customer retains all right, title, and interest in its intellectual
property, including designs, specifications, firmware, software, and
trademarks. Manufacturer shall not use Customer's IP for any purpose other
than performing Services under this Agreement.

20.2 Tooling, fixtures, and test equipment purchased or developed by
Manufacturer specifically for Customer's Products ("Customer Tooling")
shall be owned by Customer. Manufacturer shall maintain, insure, and
clearly label all Customer Tooling. Upon termination, Customer Tooling
shall be returned to Customer within thirty (30) days.

20.3 Process improvements, manufacturing know-how, and general-purpose
tooling developed by Manufacturer shall remain Manufacturer's intellectual
property.

21. COMPLIANCE AND REGULATORY

21.1 Manufacturer shall comply with all applicable federal, state, and
local laws and regulations, including but not limited to RoHS, REACH,
conflict minerals reporting (Dodd-Frank Section 1502), and California
Proposition 65.

21.2 Manufacturer shall maintain records sufficient to demonstrate
compliance with all applicable regulations and shall make such records
available to Customer upon reasonable request.

22. FORCE MAJEURE

22.1 Neither party shall be liable for delays or failures in performance
resulting from causes beyond its reasonable control, including but not
limited to natural disasters, war, terrorism, government actions, pandemic,
fire, flood, earthquake, labor disputes not involving Manufacturer's
employees, or interruption of transportation.

22.2 The affected party shall provide written notice within five (5)
business days of the force majeure event and shall use commercially
reasonable efforts to resume performance. If the force majeure event
continues for more than ninety (90) days, either party may terminate this
Agreement without liability.

23. TERMINATION FOR CAUSE

23.1 Either party may terminate this Agreement upon written notice if the
other party: (a) commits a material breach that remains uncured for thirty
(30) days after written notice specifying the breach; (b) becomes
insolvent, files for bankruptcy, or has a receiver appointed for a
substantial part of its assets; or (c) assigns this Agreement without
consent in violation of Section 25.

23.2 Upon termination for cause by Customer, Manufacturer shall complete
all work-in-process for which materials have been procured and deliver
finished Products to Customer. Customer shall pay for all conforming
finished goods and work-in-process at the agreed prices, and for committed
materials per Section 6.

24. TERMINATION FOR CONVENIENCE

24.1 Either party may terminate this Agreement for convenience upon one
hundred twenty (120) days' prior written notice. During the notice period,
both parties shall continue to perform their obligations under this
Agreement.

24.2 Upon termination for convenience by Customer, Customer shall purchase
from Manufacturer: (a) all finished goods in inventory; (b) all
work-in-process at a price reflecting the percentage of completion; (c) all
raw materials and components properly procured pursuant to authorized
forecasts or purchase orders, including NCNR materials per Section 6; and
(d) a reasonable termination charge not to exceed the lesser of five
percent (5%) of the value of cancelled orders or five hundred thousand
dollars ($500,000) to cover Manufacturer's wind-down costs.

24.3 Upon termination for convenience by Manufacturer, Manufacturer shall
provide transition assistance as described in Section 25.

25. TRANSITION ASSISTANCE

25.1 Upon any termination or expiration of this Agreement, Manufacturer
shall provide reasonable transition assistance for a period of up to six
(6) months, including: (a) continuation of production during transition;
(b) transfer of production documentation and process instructions;
(c) return of Customer Tooling per Section 20.2; (d) support for
qualification of alternative manufacturer; and (e) last-time buy
opportunity for critical components.

25.2 Customer shall compensate Manufacturer for transition assistance at
Manufacturer's standard professional services rates, unless termination
resulted from Manufacturer's material breach.

26. DISPUTE RESOLUTION AND GOVERNING LAW

26.1 The parties shall attempt to resolve any dispute arising under this
Agreement through good-faith negotiation between senior executives within
thirty (30) days of written notice of the dispute.

26.2 If negotiation fails, the dispute shall be submitted to binding
arbitration administered by the American Arbitration Association under its
Commercial Arbitration Rules. Arbitration shall take place in San
Francisco, California.

26.3 This Agreement shall be governed by and construed in accordance with
the laws of the State of California, without regard to conflict of laws
principles.

27. TERM AND RENEWAL

27.1 This Agreement shall have an initial term of three (3) years from the
Effective Date. Thereafter, the Agreement shall automatically renew for
successive one (1) year periods unless either party provides written notice
of non-renewal at least ninety (90) days prior to the expiration of the
then-current term.

27.2 The terms and conditions of this Agreement shall remain in effect for
any SOW executed during the term until all obligations under such SOW have
been fulfilled, even if this Agreement has otherwise expired.

IN WITNESS WHEREOF, the parties have executed this Agreement as of the
Effective Date.

TechVision Corporation          Precision Manufacturing Solutions Inc.
By: ________________________    By: ________________________
Name:                           Name:
Title:                          Title:
Date:                           Date:
"""


def get_demo_contract():
    """Return the demo contract text."""
    return DEMO_CONTRACT_TEXT.strip()
