def should_alert(old: str | None, new: str, levels: set[str]) -> bool:
    return new in levels and new != old
