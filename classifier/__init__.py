"""Only the scripted replay uses this small, deterministic classifier."""
import re

from entities import Company

RELATIONSHIP = re.compile(r"undisclosed relationship|workplace relationship|extramarital affair", re.I)


def classify(text: str, company: Company | None) -> tuple[bool, int]:
    hit = bool(company and RELATIONSHIP.search(text) and "CEO" in text)
    return hit, 98 if hit else 4
