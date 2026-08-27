"""Where a reader goes for what this data cannot settle.

Every entry answers two questions -- why the sources cannot say, and what to do about it --
and every one is tied to a recorded decision rather than invented at the point of use. The
catalogue lives in one place so that no page can invent a hedge of its own.
"""

FEDERAL_REGISTER = "https://www.federalregister.gov/documents/search"
CSMS = "https://www.cbp.gov/trade/automated/cargo-systems-messaging-service"
CROSS = "https://rulings.cbp.gov/"
HTS = "https://hts.usitc.gov/"

UNKNOWNS: dict[str, dict[str, str]] = {
    "stacking": {
        "question": "Do all of these additional duties apply at once, and in what order?",
        "why": (
            "The HTSUS states each duty but never how they combine. Stacking order is set by "
            "CBP in its filing instructions, which are not part of the tariff schedule and "
            "not in any of the three sources this project reads."
        ),
        "source_name": "CBP Cargo Systems Messaging Service (CSMS)",
        "url": CSMS,
        "what_to_search": "the 9903 heading numbers listed above",
    },
    "exclusion": {
        "question": "Is my product on one of these exclusion lists?",
        "why": (
            "An exclusion describes a product, not a code — the same subheading holds goods "
            "that are excluded and goods that are not. Deciding needs the goods in front of "
            "you and the note text side by side."
        ),
        "source_name": "the note text on this site, then the USTR notice that granted it",
        "url": FEDERAL_REGISTER,
        "what_to_search": "the U.S. note number shown on the exclusion, plus your product",
    },
    "special": {
        "question": "Can I claim a free-trade-agreement rate instead?",
        "why": (
            "Column 1 Special is printed here as the schedule prints it and is never "
            "interpreted. Deciding needs four things none of these sources has: the SPI code "
            "table in General Note 3(a)(iv), the rules of origin in a General Note per "
            "agreement, the importer's own claim, and for some rows chapter 98. D-0027."
        ),
        "source_name": "HTSUS General Notes",
        "url": HTS,
        "what_to_search": "the letters in brackets after 'Free' on the Special rate",
    },
    "alternatives": {
        "question": "Several duty reductions cite my code. Which one is mine?",
        "why": (
            "Subchapter II provisions are told apart by what the goods are, not by how they "
            "classify. Several cite the same subheading, each naming a different substance by "
            "CAS registry number, and the tariff code cannot choose between them."
        ),
        "source_name": "your product's CAS registry number, against the numbers listed here",
        "url": HTS,
        "what_to_search": "the CAS number on your supplier's specification sheet",
    },
    "classification": {
        "question": "Is this even the right code for my product?",
        "why": (
            "This site does not classify goods. Search matches the schedule's wording, which "
            "is not the wording anyone uses for a product, and classification is the "
            "importer's legal responsibility."
        ),
        "source_name": "CBP CROSS binding rulings",
        "url": CROSS,
        "what_to_search": "your product in plain English — rulings show how CBP decided",
    },
    "column2": {
        "question": "Does my country pay the Column 1 or the Column 2 rate?",
        "why": (
            "The countries without normal trade relations are named in General Note 3(b), "
            "which is not in any of the three sources. The four-country list this site uses "
            "is an editorial addition, marked as such."
        ),
        "source_name": "HTSUS General Note 3(b)",
        "url": HTS,
        "what_to_search": "General Note 3(b), 'Rate of Duty Column 2'",
    },
    "effectivity": {
        "question": "Is this provision still in force?",
        "why": (
            "Dates are read from the provision's own prose, which states one only when it is "
            "unusual. The PDF marks an expired row by shading it grey, and text extraction "
            "loses that entirely. D-0043."
        ),
        "source_name": "the current HTSUS revision, and the Federal Register notice",
        "url": HTS,
        "what_to_search": "the heading number, in the current revision",
    },
    "instrument": {
        "question": "What law or order actually created this duty?",
        "why": (
            "A trade action leaves three artifacts: the legal instrument, the tariff line, "
            "and the filing instruction. This dataset has only the middle one."
        ),
        "source_name": "Federal Register",
        "url": FEDERAL_REGISTER,
        "what_to_search": "the 9903 heading number",
    },
    "origin_scoped": {
        "question": "Do these provisions actually cover my goods?",
        "why": (
            "Each of these names your country of origin but limits the goods in prose rather "
            "than by code — \"Aluminum articles that are the product of Russia\", for "
            "instance. Nothing in the data ties that wording to a subheading, so they are "
            "listed but left out of the total. Read the text against your shipment."
        ),
        "source_name": "the provision text shown above",
        "url": HTS,
        "what_to_search": "the heading number, then read what it says it applies to",
    },
    "origin_unresolved": {
        "question": "Is my country of origin inside the set this provision names?",
        "why": (
            "Each of these limits itself to a group of countries the schedule does not list "
            "here — \"any country identified in general note 3(b)\", \"any country not exempt "
            "under U.S. note 41(c)\", \"any country determined by CBP to have been "
            "transshipped\". The list lives in a document none of the three sources contains, "
            "so whether yours is in it cannot be answered here. Shown and left out of the "
            "figure. D-0056."
        ),
        "source_name": "the General Note or U.S. note the provision names",
        "url": HTS,
        "what_to_search": "the note number quoted in the provision, then your country",
    },
    "competing_replacements": {
        "question": "Two provisions both replace the base rate. Which one is mine?",
        "why": (
            "U.S. note 1 to subchapter III says a Chapter 99 rate applies in lieu of the rate "
            "in chapters 1 to 98 — so two of them cannot both apply, and the schedule does "
            "not choose. These are usually a tariff-rate quota's in-quota and over-quota "
            "rates, told apart by how much of the quota has already been filled this year, "
            "which is not in any of these sources. The lower one is in the figure and the "
            "rest are in the range."
        ),
        "source_name": "the quota status published by CBP",
        "url": CSMS,
        "what_to_search": "the heading numbers above, plus 'tariff rate quota'",
    },
    "scope_widened": {
        "question": "Why does this provision look like it covers so much?",
        "why": (
            "It cites a subdivision of a U.S. note that the notes parser could not isolate "
            "from the PDF, so the coverage shown is the whole note — wider than the "
            "provision really is. D-0038."
        ),
        "source_name": "the note text and page number shown on the provision",
        "url": HTS,
        "what_to_search": "the subdivision named in the provision, in the notes PDF",
    },
}
