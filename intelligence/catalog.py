"""
Fixed field schemas. One LLM call per group returns JSON for all its fields, so
results are consistent between tenders (which is what makes comparison possible).
Each field has its own retrieval query.
"""


def F(key, label, hint, query):
    return {"key": key, "label": label, "hint": hint, "query": query}


GROUPS = {
    "key_info": {
        "title": "Key tender details", "risk": False, "k_each": 3, "max_total": 22,
        "fields": [
            F("title", "Name of work and tender number", "title, NIT / tender reference number", "name of work tender notice NIT number reference"),
            F("authority", "Issuing authority", "department or organisation inviting the tender", "tender inviting authority department executive engineer office"),
            F("estimated_cost", "Estimated cost", "estimated cost / cost put to tender", "estimated cost of work cost put to tender"),
            F("emd", "Earnest money deposit (EMD)", "amount and mode of payment", "earnest money deposit EMD amount mode of payment"),
            F("tender_fee", "Tender document fee", "cost of tender documents (may be free) and any e-tender processing fee", "cost of tender document free of cost downloaded processing fee"),
            F("performance_guarantee", "Performance guarantee", "percentage of tendered value, form and time to submit", "performance guarantee percentage of tendered value schedule E"),
            F("security_deposit", "Security deposit", "percentage of tendered value and how it is recovered", "security deposit percentage of tendered value deducted from bills"),
            F("completion_period", "Completion period", "time allowed, start of period, exclusions such as monsoon", "time allowed for execution of work months from date of start schedule F period of completion"),
            F("bid_deadline", "Last date and time for bid submission", "date and time", "last date and time of submission of bids online"),
            F("prebid_meeting", "Pre-bid meeting", "date, time and venue", "pre-bid meeting date time venue"),
            F("bid_opening", "Bid opening date", "technical and financial bid opening", "date of opening of technical bid financial bid"),
            F("bid_validity", "Bid validity", "number of days the bid must remain open for acceptance", "bids shall remain open for acceptance for a period of days from the date of opening of bids"),
        ],
    },
    "eligibility": {
        "title": "Bidder eligibility criteria", "risk": False, "k_each": 3, "max_total": 22,
        "fields": [
            F("who_can_bid", "Who may bid", "category and class of contractor allowed to bid, and any restriction to enlisted contractors", "invites online percentage rate bids from eligible contractors enlisted in category appropriate class"),
            F("turnover", "Minimum annual turnover", "amount, number of years, which financial years", "minimum average annual turnover last three financial years eligibility"),
            F("similar_work", "Similar work experience", "number of works, value, period; say WHO it applies to (for example non-enlisted contractors only) and if the amounts are left blank", "experience of similar works completed value in last seven years"),
            F("net_worth", "Net worth, solvency and profitability", "requirements and certificates", "net worth solvency certificate profit eligibility"),
            F("registration", "Contractor registration / class", "enlistment class, licence, category", "contractor registration class enlistment licence category"),
            F("statutory", "Statutory registrations", "GST, PAN, EPF, ESI, labour licence, ISO", "GST PAN EPF ESI registration labour licence ISO certificate"),
            F("equipment", "Key equipment", "machinery the bidder must own or have access to", "plant machinery equipment testing equipment to be provided by the contractor at site lab Vernier caliper megger tools and tackles"),
            F("personnel", "Key personnel", "engineers and staff with qualifications and experience", "key personnel engineer qualification experience technical staff"),
            F("jv", "Joint venture / consortium", "allowed or not, conditions", "joint venture consortium permitted conditions"),
            F("bid_capacity", "Available bid capacity", "formula, if stated", "available bid capacity formula pending works"),
        ],
    },
    "risks": {
        "title": "Risk and compliance", "risk": True, "k_each": 3, "max_total": 22,
        "fields": [
            F("liquidated_damages", "Liquidated damages / penalty", "rate per day or week and maximum cap", "compensation for delay clause 2 liquidated damages per cent per month of delay maximum percent authority for fixing compensation"),
            F("termination", "Termination and foreclosure", "grounds, consequences, forfeiture of security", "termination of contract rescind abandoned contract contractor default foreclosure of work"),
            F("price_variation", "Price variation / escalation", "allowed or fixed price (say rates are firm if so), formula", "price variation escalation not payable rates firm and inclusive fixed price"),
            F("payment_terms", "Payment terms", "milestones, running bills, time to pay", "payment running account bill interim payment within days"),
            F("retention", "Retention money", "percentage and release conditions", "retention money deduction percentage release"),
            F("defect_liability", "Defect liability and warranty", "period and obligations", "defect liability period guarantee for a period of months from date of acceptance warranty maintenance"),
            F("onerous", "Other onerous clauses", "indemnity, insurance, arbitration, unusual conditions", "indemnity insurance arbitration dispute special conditions"),
        ],
    },
    "boq": {
        "title": "BOQ and pricing", "risk": False, "k_each": 3, "max_total": 20,
        "fields": [
            F("contract_type", "Contract and rate type", "item rate, percentage rate or lump sum", "item rate percentage rate lump sum contract schedule"),
            F("boq_items", "Main BOQ items", "main items with quantity and unit as a Markdown bullet list (max 12); many tenders call this the Schedule of Quantity", "schedule of quantity bill of quantities sl no description of item qty unit amount sub-head grand total"),
            F("taxes", "Taxes and duties", "GST and other taxes: included or extra", "GST taxes duties inclusive exclusive rates quoted"),
            F("deviation", "Extra items and deviation limits", "limits and rates for extra or substituted items", "extra items deviation limit quantity variation substituted items"),
            F("quoting_rules", "Rules for quoting rates", "how to fill the BOQ, tolerance, rounding", "instructions for filling rates BOQ quote above below"),
        ],
    },
}
