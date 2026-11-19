import hashlib
import html
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup


def plain(value: str, limit: int = 720) -> str:
    string = html.unescape(str(value or ""))
    if "<" in string:
        string = BeautifulSoup(string, "html.parser").get_text(" ", strip=True)
    return " ".join(string.split())[:limit]


def epoch(value: str | int | float | None) -> int | None:
    if isinstance(value, (float, int)):
        return int(value)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        try:
            parsed = parsedate_to_datetime(value)
        except (ValueError, TypeError, OverflowError):
            return None
    return int(parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).timestamp())


def canonical(url: str) -> str:
    try:
        p = urlsplit(url)
        if (
            p.scheme not in ("http", "https")
            or not p.hostname
            or p.username
            or p.password
        ):
            return ""
        query = [
            (k, v)
            for k, v in parse_qsl(p.query, keep_blank_values=True)
            if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}
        ]
        return urlunsplit(
            (
                p.scheme.lower(),
                p.netloc.lower(),
                p.path or "/",
                urlencode(sorted(query)),
                "",
            )
        )
    except ValueError:
        return ""


def key(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:24]


RELATIONSHIP = re.compile(
    r"\b(affair|extramarital|inappropriate relationship|undisclosed relationship|consensual relationship|workplace relationship|personal relationship|romantic relationship|infidelity|fraternization)\b",
    re.I,
)
