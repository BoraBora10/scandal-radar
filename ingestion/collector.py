import asyncio
import os
import time
from pathlib import Path

import httpx

from entities.directory import CACHE, Directory
from ingestion.jetstream import Jetstream
from ingestion.records import epoch
from ingestion.sec import EdgarPoller
from ingestion.store import Store

CHANNELS = [
    ("google", "Google News", "RSS", 60),
    ("pr", "PR Newswire", "RSS", 60),
    ("business", "Business Wire", "RSS", 60),
    ("globe", "GlobeNewswire", "RSS", 60),
    ("sec", "SEC EDGAR", "8-K", 6),
    ("bluesky", "Bluesky", "WS", 5),
    ("gdelt", "GDELT", "DOC", 900),
    ("finnhub", "Finnhub", "API", 60),
]


class Collector:
    def __init__(self, root: Path):
        self.directory = Directory()
        self.store = Store(
            root / ".data" / "news.sqlite", int(os.getenv("MAX_ITEM_AGE", "21600"))
        )
        if self.store.max_age <= 0:
            raise ValueError("MAX_ITEM_AGE must be positive seconds")
        self.store.refresh_matches(self.directory.index)
        self.status = {
            key: dict(
                key=key,
                name=name,
                protocol=kind,
                state="starting",
                last_at=None,
                last_ok=None,
                scanned=0,
                added=0,
                error="",
                interval=period,
            )
            for key, name, kind, period in CHANNELS
        }
        sec_contact = os.getenv("SEC_USER_AGENT", "").strip()
        self.edgar = EdgarPoller(sec_contact) if sec_contact else None
        self.key = os.getenv("FINNHUB_API_KEY", "")
        self.http = httpx.AsyncClient(
            timeout=httpx.Timeout(18, connect=8),
            follow_redirects=True,
            headers={
                "User-Agent": "ScandalRadar/0.2 (private news reader)",
                "Accept": "*/*",
            },
        )
        self.tasks = []

    def start(self) -> None:
        self.tasks = [
            asyncio.create_task(self.poll(key, seconds))
            for key, _, _, seconds in CHANNELS
            if key != "bluesky"
        ]
        self.tasks.extend(
            [
                asyncio.create_task(self.social()),
                asyncio.create_task(self.refresh_directory()),
            ]
        )

    async def close(self) -> None:
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        await self.http.aclose()
        self.store.db.close()

    def commit(self, name: str, batch: dict, cursor=None) -> None:
        now = int(time.time())
        added = self.store.put(
            name,
            batch["items"],
            batch["scanned"],
            self.directory.index,
            now,
            None if cursor is None else str(cursor),
        )
        row = self.status[name]
        state = batch["state"]
        row.update(
            state=state,
            last_at=now,
            scanned=batch["scanned"],
            added=added,
            error=batch.get("error", ""),
            retry_after=batch.get("retry_after", 0),
        )
        if state == "online" or batch["scanned"] or batch.get("checked"):
            row["last_ok"] = now
        if name == "sec":
            row["checked"] = batch.get("checked", 0)

    async def poll(self, name: str, period: int) -> None:
        from ingestion.news import fetch_news

        failures = 0
        if name == "sec" and self.edgar is None:
            self.status[name].update(
                state="disabled", error="Set SEC_USER_AGENT in .env to enable filings"
            )
            return
        if name == "finnhub" and not self.key:
            self.status[name].update(
                state="disabled", error="Optional free API key required"
            )
            return
        cursor = int(self.store.cursor(name) or 0)
        while True:
            began = time.monotonic()
            try:
                if name == "sec":
                    batch = await self.edgar.poll(
                        self.directory.index.companies,
                        max_age_seconds=self.store.max_age,
                    )
                else:
                    batch = await fetch_news(
                        name,
                        self.http,
                        symbols=list(self.directory.index.symbols),
                        finnhub_token=self.key,
                        cursor=cursor,
                        max_age_hours=self.store.max_age / 3600,
                    )
                cursor = batch.get("next_cursor", cursor)
                self.commit(name, batch, cursor if name == "finnhub" else None)
                failures = (
                    failures + 1
                    if batch["state"] in {"error", "backoff", "degraded"}
                    else 0
                )
                delay = (
                    max(
                        batch.get("retry_after") or 0,
                        min(1800, period * 2 ** min(5, failures)),
                    )
                    if failures
                    else period
                )
            except Exception as exc:
                self.status[name].update(
                    state="error", last_at=int(time.time()), error=type(exc).__name__
                )
                failures += 1
                delay = min(1800, period * 2 ** min(failures, 5))
            await asyncio.sleep(max(1, delay - (time.monotonic() - began)))

    async def social(self) -> None:
        cursor = self.store.cursor("bluesky")
        stream = Jetstream(cursor=int(cursor) if cursor else None)
        while True:
            try:
                async for batch in stream.batches(max_age_seconds=self.store.max_age):
                    self.commit("bluesky", batch, batch.get("cursor"))
            except Exception as exc:
                self.status["bluesky"].update(
                    state="error", error=type(exc).__name__, last_at=int(time.time())
                )
                await asyncio.sleep(30)

    async def refresh_directory(self) -> None:
        from entities.refresh_directory import refresh_directory
        import json

        while True:
            try:
                last = epoch(self.directory.data["fetched_at"]) or 0
                await asyncio.sleep(max(0, 86400 - (time.time() - last)))
                data = await asyncio.to_thread(refresh_directory)
                # Refuse incomplete constituent tables and avoid losing the last complete snapshot.
                if not 480 <= len(data["companies"]) <= 530:
                    raise ValueError("Unexpected constituent count")
                self.directory.install(data)
                self.store.refresh_matches(self.directory.index)
                tmp = CACHE.with_suffix(".tmp")
                tmp.write_text(json.dumps(data))
                tmp.replace(CACHE)
            except Exception as exc:
                self.directory.error = f"Refresh deferred ({type(exc).__name__})"
                await asyncio.sleep(900)

    def snapshot(self) -> dict:
        return self.store.snapshot(
            list(self.status.values()),
            {**self.directory.summary, "error": self.directory.error},
        )
