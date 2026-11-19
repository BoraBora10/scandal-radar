"""Fictional company directory and deterministic demo matching."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Company:
    ticker: str
    name: str
    ceo: str


COMPANIES = [
    Company("HLVD", "Halvorsen Dynamics", "Mark Brenner"),
    Company("TVG.D", "Torven Grid", "Elin Voss"),
    Company("MVL.D", "Morrow Vale", "Ada Tern"),
    Company("KSN.D", "Kestrel Nine", "Luca Venn"),
]


def match_company(text: str) -> Company | None:
    normalized = text.casefold()
    return next((company for company in COMPANIES if company.name.casefold() in normalized
                 and company.ceo.casefold() in normalized), None)
