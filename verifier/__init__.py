from collections.abc import Sequence


def verification(evidence: Sequence[dict]) -> str:
    reports = {item["publisher"] for item in evidence if item["kind"] == "report"}
    if len(reports) >= 2 or any(item["trusted"] for item in evidence):
        return "verified"
    return "developing" if reports or any(i["kind"] == "filing" for i in evidence) else "rumor"
