"""Headline-only feeds for a personal news reader. All URLs are provider endpoints."""

from __future__ import annotations

import asyncio
import calendar
import json
import math
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import httpx

from ingestion.records import canonical, plain

RSS = {
    "pr": ("PR Newswire", "https://www.prnewswire.com/rss/news-releases-list.rss"),
    "business": (
        "Business Wire",
        "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeEFxRXA==",
    ),
    "globe": (
        "GlobeNewswire",
        "https://www.globenewswire.com/RssFeed/orgclass/1/feedTitle/GlobeNewswire%20-%20News%20about%20Public%20Companies",
    ),
}
GOOGLE = "https://news.google.com/rss/search"
QUERIES = (
    '"CEO" "affair"',
    '"CEO" "extramarital"',
    '"CEO" "inappropriate relationship"',
    '"CEO" "undisclosed relationship"',
    '"CEO" resigns relationship',
    '"chief executive" affair',
    '"chief executive" "personal relationship"',
    '"chief executive" "romantic relationship"',
    '"CEO" "workplace relationship"',
    '"CEO" "consensual relationship"',
)
GDELT = "https://api.gdeltproject.org/api/v2/doc/doc"
FINNHUB = "https://finnhub.io/api/v1/company-news"
MAX_BYTES = 3_000_000
FETCH_TIMEOUT = 15


class FeedError(Exception):
    def __init__(self, message: str, retry_after: int = 0, status_code: int = 0):
        super().__init__(message)
        self.retry_after = retry_after
        self.status_code = status_code


def retry_seconds(value: str | None, fallback: int) -> int:
    if value:
        if value.isdecimal() and len(value) < 10:
            return max(1, int(value))
        try:
            expires = parsedate_to_datetime(value)
            if expires.tzinfo is not None:
                return max(
                    1, math.ceil((expires - datetime.now(timezone.utc)).total_seconds())
                )
        except (TypeError, ValueError, OverflowError):
            pass
    return fallback


async def download(
    client: httpx.AsyncClient, url: str, params: dict | None = None
) -> bytes:
    try:
        async with asyncio.timeout(FETCH_TIMEOUT):
            # The pinned endpoints are HTTPS. Never forward credentials to a redirect target.
            async with client.stream(
                "GET", url, params=params, follow_redirects=False
            ) as response:
                if response.status_code != 200:
                    fallback = 300 if response.status_code in (429, 503) else 0
                    retry = retry_seconds(response.headers.get("Retry-After"), fallback)
                    raise FeedError(
                        f"HTTP {response.status_code}", retry, response.status_code
                    )
                body = bytearray()
                async for chunk in response.aiter_bytes(chunk_size=32768):
                    if len(body) + len(chunk) > MAX_BYTES:
                        raise FeedError("Feed exceeds the size limit")
                    body.extend(chunk)
                return bytes(body)
    except (httpx.RequestError, TimeoutError) as exc:
        # An HTTP client's exception message can include request parameters.
        raise FeedError(
            "Request timed out"
            if isinstance(exc, (TimeoutError, httpx.TimeoutException))
            else "Network request failed"
        ) from None


def row(
    source: str,
    title: str,
    url: str,
    publisher: str,
    text: str,
    published: datetime | None,
    start: datetime,
    end: datetime,
    author: str = "",
    basis: str = "published",
) -> dict | None:
    if published is None or not start <= published <= end or not canonical(url):
        return None
    headline = plain(title, 320)
    if not headline:
        return None
    return {
        "source": source,
        "url": url,
        "author": plain(author, 120),
        "publisher": plain(publisher, 120),
        "published_at": published.isoformat().replace("+00:00", "Z"),
        "title": headline,
        "text": plain(text),
        "kind": "news",
        "time_basis": basis,
    }


def parse_rss(
    body: bytes, key: str, label: str, start: datetime, end: datetime
) -> tuple[int, list[dict]]:
    feed = feedparser.parse(body, resolve_relative_uris=False)
    if not feed.version or (feed.bozo and not feed.entries):
        raise FeedError("Provider returned an invalid RSS/Atom feed")
    rows = []
    for entry in feed.entries:
        date = entry.get("published_parsed")
        if not date:
            continue
        try:
            published = datetime.fromtimestamp(calendar.timegm(date), timezone.utc)
        except (TypeError, OverflowError, ValueError, OSError):
            continue
        publisher = (
            (entry.get("source") or {}).get("title") or entry.get("publisher") or label
        )
        item = row(
            key,
            entry.get("title", ""),
            entry.get("link", ""),
            publisher,
            entry.get("summary", ""),
            published,
            start,
            end,
            entry.get("author", ""),
        )
        if item:
            rows.append(item)
    return len(feed.entries), rows


def parse_json(body: bytes) -> Any:
    try:
        return json.loads(body)
    except (ValueError, UnicodeError):
        raise FeedError("Provider returned an invalid JSON response") from None


def parse_gdelt(body: bytes, start: datetime, end: datetime) -> tuple[int, list[dict]]:
    payload = parse_json(body)
    articles = payload.get("articles") if isinstance(payload, dict) else None
    if not isinstance(articles, list):
        raise FeedError("GDELT article list is unavailable")
    items = []
    for article in articles:
        if not isinstance(article, dict):
            continue
        try:
            seen = datetime.strptime(article["seendate"], "%Y%m%dT%H%M%SZ").replace(
                tzinfo=timezone.utc
            )
        except (TypeError, KeyError, ValueError):
            continue
        title = article.get("title", "")
        result = row(
            "gdelt",
            title,
            article.get("url", ""),
            article.get("domain", ""),
            "",
            seen,
            start,
            end,
            basis="first_seen",
        )
        if result:
            items.append(result)
    return len(articles), items


def parse_finnhub(
    body: bytes, start: datetime, end: datetime
) -> tuple[int, list[dict]]:
    articles = parse_json(body)
    if not isinstance(articles, list):
        raise FeedError("Finnhub news list is unavailable")
    items = []
    for article in articles:
        if not isinstance(article, dict):
            continue
        try:
            published = datetime.fromtimestamp(article["datetime"], timezone.utc)
        except (OverflowError, TypeError, KeyError, ValueError, OSError):
            continue
        result = row(
            "finnhub",
            article.get("headline", ""),
            article.get("url", ""),
            article.get("source", ""),
            article.get("summary", ""),
            published,
            start,
            end,
        )
        if result:
            items.append(result)
    return len(articles), items


async def fetch_news(
    key: str,
    client: httpx.AsyncClient,
    *,
    symbols: Sequence[str] = (),
    finnhub_token: str | None = None,
    cursor: int = 0,
    max_age_hours: float = 6,
    now: datetime | None = None,
) -> dict:
    """Poll one adapter. A numeric cursor resumes Finnhub's round-robin symbol scan."""
    end = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    start = end - timedelta(hours=max_age_hours)
    result: dict[str, Any] = {
        "items": [],
        "scanned": 0,
        "state": "online",
        "error": "",
        "retry_after": 0,
    }
    # Batches keep concurrency bounded and stop further dispatch when a provider asks to slow down.
    width = 1
    if key == "google":
        jobs = [
            (GOOGLE, {"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"})
            for q in QUERIES
        ]
        width = 2
    elif key in RSS:
        jobs = [(RSS[key][1], None)]
    elif key == "gdelt":
        jobs = [
            (
                GDELT,
                {
                    "query": '(CEO OR "chief executive") (affair OR infidelity OR "inappropriate relationship" OR "undisclosed relationship")',
                    "format": "json",
                    "mode": "artlist",
                    "timespan": f"{max(15, math.ceil(max_age_hours * 60))}min",
                    "sort": "datedesc",
                    "maxrecords": "100",
                },
            )
        ]
    elif key == "finnhub":
        result["next_cursor"] = int(cursor)
        if not finnhub_token:
            return {**result, "state": "disabled", "error": "Optional API key is unset"}
        if not symbols:
            return {
                **result,
                "state": "waiting",
                "error": "Waiting for the company directory",
            }
        # At a 60-second poll interval, 10 sequential calls/minute is below the free limit of 60.
        jobs = [
            (
                FINNHUB,
                {
                    "symbol": symbols[(int(cursor) + i) % len(symbols)],
                    "from": start.date().isoformat(),
                    "to": end.date().isoformat(),
                    "token": finnhub_token,
                },
            )
            for i in range(min(10, len(symbols)))
        ]
    else:
        raise ValueError(f"Unknown news source {key!r}")

    async def fetch_one(url: str, params: dict | None) -> tuple[int, list[dict]]:
        body = await download(client, url, params)
        if key == "gdelt":
            return parse_gdelt(body, start, end)
        if key == "finnhub":
            return parse_finnhub(body, start, end)
        label = RSS[key][0] if key in RSS else "Google News"
        return await asyncio.to_thread(parse_rss, body, key, label, start, end)

    successes = 0
    failures = 0
    unique: dict[str, dict] = {}
    for offset in range(0, len(jobs), width):
        responses = await asyncio.gather(
            *(fetch_one(u, p) for u, p in jobs[offset : offset + width]),
            return_exceptions=True,
        )
        stop = False
        for outcome in responses:
            if isinstance(outcome, BaseException):
                if not isinstance(outcome, FeedError):
                    raise outcome
                failures += 1
                result["error"] = str(outcome)
                result["retry_after"] = max(result["retry_after"], outcome.retry_after)
                stop = (
                    stop
                    or bool(outcome.retry_after)
                    or outcome.status_code in (401, 403)
                )
                if key == "finnhub" and not stop:
                    result["next_cursor"] = (int(cursor) + offset + 1) % len(symbols)
            else:
                scanned, items = outcome
                successes += 1
                result["scanned"] += scanned
                for item in items:
                    unique.setdefault(canonical(item["url"]), item)
                if key == "finnhub":
                    result["next_cursor"] = (int(cursor) + offset + 1) % len(symbols)
        if stop:
            break
    result["items"] = sorted(
        unique.values(), key=lambda it: it["published_at"], reverse=True
    )
    if failures:
        result["state"] = "degraded" if successes else "error"
    return result
