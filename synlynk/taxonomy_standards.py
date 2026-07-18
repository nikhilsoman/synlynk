"""Static lookup tables for external taxonomy standards.

This module provides a curated subset of:
- NAICS for industry/domain
- APQC PCF for functional discipline
- SFIA for technical competency

The tables intentionally cover software and product work only. They are not
complete copies of the underlying standards.
"""

NAICS_CODES = {
    "none": {"label": "Not industry-specific", "parent": None},
    "51": {"label": "Information", "parent": None},
    "5112": {"label": "Software Publishers", "parent": "51"},
    "5182": {"label": "Data Processing, Hosting, and Related Services", "parent": "51"},
    "5191": {"label": "Other Information Services", "parent": "51"},
    "54": {"label": "Professional, Scientific, and Technical Services", "parent": None},
    "5415": {"label": "Computer Systems Design and Related Services", "parent": "54"},
    "5413": {"label": "Architectural, Engineering, and Related Services", "parent": "54"},
    "52": {"label": "Finance and Insurance", "parent": None},
    "5221": {"label": "Depository Credit Intermediation", "parent": "52"},
    "5242": {"label": "Insurance Agencies and Brokerages", "parent": "52"},
    "62": {"label": "Health Care and Social Assistance", "parent": None},
    "6211": {"label": "Offices of Physicians", "parent": "62"},
    "61": {"label": "Educational Services", "parent": None},
    "6117": {"label": "Educational Support Services", "parent": "61"},
    "44-45": {"label": "Retail Trade", "parent": None},
    "4541": {"label": "Electronic Shopping and Mail-Order Houses", "parent": "44-45"},
    "31-33": {"label": "Manufacturing", "parent": None},
    "3345": {"label": "Navigational, Measuring, Electromedical, and Control Instruments Manufacturing", "parent": "31-33"},
    "48-49": {"label": "Transportation and Warehousing", "parent": None},
    "22": {"label": "Utilities", "parent": None},
}

APQC_CODES = {
    "1.0": {"label": "Develop Vision and Strategy", "parent": None},
    "2.0": {"label": "Develop and Manage Products and Services", "parent": None},
    "2.1": {"label": "Develop and Manage Product Portfolio", "parent": "2.0"},
    "2.2": {"label": "Design Products and Services", "parent": "2.0"},
    "2.3": {"label": "Develop Products and Services", "parent": "2.0"},
    "2.4": {"label": "Manage Product Lifecycle", "parent": "2.0"},
    "3.0": {"label": "Market and Sell Products and Services", "parent": None},
    "5.0": {"label": "Deliver Services", "parent": None},
    "6.0": {"label": "Manage Customer Service", "parent": None},
    "7.0": {"label": "Develop and Manage Human Capital", "parent": None},
    "8.0": {"label": "Manage Information Technology", "parent": None},
    "8.1": {"label": "Develop and Manage IT Customer Relationships", "parent": "8.0"},
    "8.2": {"label": "Develop and Manage IT Strategy and Governance", "parent": "8.0"},
    "8.3": {"label": "Develop and Implement Security, Privacy, and Data Protection Controls", "parent": "8.0"},
    "8.4": {"label": "Manage Enterprise Information", "parent": "8.0"},
    "8.5": {"label": "Develop and Maintain Information Technology Solutions", "parent": "8.0"},
    "8.6": {"label": "Deploy Information Technology Solutions", "parent": "8.0"},
    "8.7": {"label": "Deliver and Support Information Technology Services", "parent": "8.0"},
    "9.0": {"label": "Manage Financial Resources", "parent": None},
    "10.0": {"label": "Acquire, Construct, and Manage Assets", "parent": None},
    "11.0": {"label": "Manage Enterprise Risk, Compliance, and Resiliency", "parent": None},
}

SFIA_CODES = {
    "PROG": {"label": "Programming/Software Development", "parent": None},
    "TEST": {"label": "Testing", "parent": None},
    "REQM": {"label": "Requirements Definition and Management", "parent": None},
    "ARCH": {"label": "Solution Architecture", "parent": None},
    "BUSA": {"label": "Business Analysis", "parent": None},
    "DBDS": {"label": "Database Design", "parent": None},
    "DTAN": {"label": "Data Analysis", "parent": None},
    "SINT": {"label": "Systems Integration", "parent": None},
    "DEPL": {"label": "Software Deployment", "parent": None},
    "ITOP": {"label": "IT Infrastructure Operations", "parent": None},
    "SCTY": {"label": "Information Security", "parent": None},
    "PEDP": {"label": "Performance Engineering", "parent": None},
    "METL": {"label": "Methods and Tools", "parent": None},
    "QUAL": {"label": "Quality Management", "parent": None},
    "PROD": {"label": "Product Management", "parent": None},
    "DLMG": {"label": "Delivery Management", "parent": None},
    "UNAN": {"label": "User Experience Analysis", "parent": None},
    "HCEV": {"label": "Human Factors Integration", "parent": None},
    "DESN": {"label": "Systems Design", "parent": None},
    "PORT": {"label": "Portfolio Management", "parent": None},
    "EMRG": {"label": "Emerging Technology Monitoring", "parent": None},
}

_AXIS_TABLES = {
    "naics": NAICS_CODES,
    "apqc": APQC_CODES,
    "sfia": SFIA_CODES,
}


def _taxonomy_label(axis: str, code: str) -> str:
    """Return the human-readable label for a taxonomy code.

    Unknown codes fall back to the raw code so legacy or unmapped values stay
    printable. Unknown axes raise ValueError to surface programming errors.
    """
    if axis not in _AXIS_TABLES:
        raise ValueError(f"Unknown taxonomy axis: {axis!r}")

    entry = _AXIS_TABLES[axis].get(code)
    if entry is None:
        return code
    return entry["label"]
