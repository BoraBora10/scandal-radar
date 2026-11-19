"""Small, rotating EDGAR submissions poller. Keep one instance per scanner process."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from time import monotonic
from typing import Any, Mapping, Sequence
import httpx
from urllib.parse import quote

SUBMISSIONS = "https://data.sec.gov/submissions/CIK{}.json"
MAX_BYTES = 12_000_000


def parse_filings(
    data: dict, companies: Sequence[Mapping], since: float, now: float
) -> list[dict]:
    """Read SEC's columnar recent filings and link the primary document."""
    cik = str(data["cik"]).zfill(10)
    if not companies or cik != str(companies[0]["cik"]).zfill(10):
        raise ValueError("Unexpected EDGAR issuer CIK")
    recent = data["filings"]["recent"]
    fields = (
        "form",
        "items",
        "acceptanceDateTime",
        "accessionNumber",
        "primaryDocument",
    )
    rows = zip(*(recent[field] for field in fields), strict=True)
    found = []
    for form, items, accepted, accession, document in rows:
        if form not in {"8-K", "8-K/A"} or "5.02" not in re.findall(
            r"\b\d+\.\d+\b", items or ""
        ):
            continue
        accepted_at = datetime.fromisoformat(accepted.replace("Z", "+00:00"))
        if accepted_at.tzinfo is None or not since <= accepted_at.timestamp() <= now:
            continue
        if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession):
            continue
        symbols = sorted({str(c["ticker"]) for c in companies})
        issuer = str(data["name"])
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{quote(document, safe='/')}"
        found.append(
            {
                "source": "SEC EDGAR",
                "author": issuer,
                "url": url,
                "kind": "filing",
                "title": f"{issuer} files Form {form} with Item 5.02",
                "text": f"Form {form} lists item(s) {items}. Item 5.02 covers director or officer changes and certain compensation arrangements.",
                "published_at": accepted_at.astimezone(timezone.utc).isoformat(),
                "matched_ticker": symbols[0],
                "company": issuer,
                "tickers": symbols,
                "cik": cik,
                "accession": accession,
                "item": "5.02",
            }
        )
    return found


async def _get(
    client: httpx.AsyncClient, cik: str, validators: dict[str, str]
) -> tuple[dict | None, dict[str, str]]:
    response = await client.get(SUBMISSIONS.format(cik), headers=validators)
    if response.status_code == 304:
        return None, validators
    response.raise_for_status()
    if len(response.content) > MAX_BYTES:
        raise ValueError("EDGAR response exceeded size limit")
    updated = {}
    for response_key, request_key in (
        ("ETag", "If-None-Match"),
        ("Last-Modified", "If-Modified-Since"),
    ):
        if response.headers.get(response_key):
            updated[request_key] = response.headers[response_key]
    return response.json(), updated


def _cooldown(error: httpx.HTTPStatusError) -> float:
    retry = error.response.headers.get("Retry-After", "")
    if retry.isdecimal():
        return max(1, int(retry))
    try:
        return max(
            1,
            parsedate_to_datetime(retry).timestamp()
            - datetime.now(timezone.utc).timestamp(),
        )
    except (TypeError, ValueError, OverflowError):
        return 600


class EdgarPoller:
    def __init__(self, user_agent: str, requests_per_second: float = 4):
        self.user_agent = user_agent
        self.interval = 1 / min(5.0, max(0.1, requests_per_second))
        self._lock = asyncio.Lock()
        self._next_request = 0.0
        self._resume_at = 0.0
        self._cursor = 0
        self._validators: dict[str, dict[str, str]] = {}

    async def poll(
        self,
        companies: Sequence[Mapping[str, Any]],
        *,
        max_age_seconds: float = 21600,
        batch_size: int = 24,
    ) -> dict:
        """Scan the next distinct CIKs. Call again promptly to complete round-robin coverage."""
        by_cik: dict[str, list[Mapping]] = {}
        for company in companies:
            cik = str(company.get("cik", ""))
            if (
                company.get("ticker")
                and cik.isdecimal()
                and 0 < int(cik) <= 9_999_999_999
            ):
                by_cik.setdefault(cik.zfill(10), []).append(company)
        ciks = sorted(by_cik)
        result = {
            "items": [],
            "scanned": 0,
            "checked": 0,
            "universe": len(ciks),
            "state": "online" if ciks else "waiting",
            "error": "",
            "retry_after": 0,
        }
        if not ciks:
            return result
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
        }
        async with self._lock, httpx.AsyncClient(headers=headers, timeout=10) as client:
            for _ in range(min(len(ciks), max(1, batch_size))):
                if monotonic() < self._resume_at:
                    result.update(
                        state="backoff",
                        error="SEC fair-access cooldown",
                        retry_after=round(self._resume_at - monotonic()) + 1,
                    )
                    break
                cik = ciks[self._cursor % len(ciks)]
                self._cursor = (self._cursor + 1) % len(ciks)
                await asyncio.sleep(max(0, self._next_request - monotonic()))
                self._next_request = monotonic() + self.interval
                try:
                    data, validators = await _get(
                        client, cik, self._validators.get(cik, {})
                    )
                    if data is not None:
                        now = datetime.now(timezone.utc).timestamp()
                        result["items"].extend(
                            parse_filings(data, by_cik[cik], now - max_age_seconds, now)
                        )
                        result["scanned"] += len(data["filings"]["recent"]["form"])
                    self._validators[cik] = validators
                    result["checked"] += 1
                except httpx.HTTPStatusError as error:
                    result.update(
                        state="degraded", error=f"SEC HTTP {error.response.status_code}"
                    )
                    if error.response.status_code in {403, 429, 503}:
                        delay = _cooldown(error)
                        self._resume_at = monotonic() + delay
                        result.update(state="backoff", retry_after=round(delay))
                        break
                except (
                    httpx.RequestError,
                    OSError,
                    ValueError,
                    KeyError,
                    TypeError,
                ) as error:
                    result.update(state="degraded", error=f"SEC {type(error).__name__}")
                    break
        return result
