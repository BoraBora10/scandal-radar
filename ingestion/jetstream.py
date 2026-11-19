"""Keyword-filtered Bluesky v2 Jetstream batches, with inclusive cursor recovery."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timezone
from time import monotonic, time
from urllib.parse import quote, urlencode

from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus, WebSocketException

ENDPOINT = (
    "wss://jetstream.us-east.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents"
)
TERMS = re.compile(
    r"\b(?:affair|infidelity|extramarital|undisclosed relationship|"
    r"inappropriate relationship|workplace relationship|consensual relationship|"
    r"interpersonal relationship|romantic relationship)\b",
    re.I,
)


def normalize_post(
    event: dict, cutoff: float, now: float, keyword: Callable[[str], bool]
) -> dict | None:
    if (
        event.get("operation") not in {"create", "update"}
        or event.get("collection") != "app.bsky.feed.post"
    ):
        return None
    record = event.get("record") or {}
    text = record.get("text")
    if not isinstance(text, str) or not keyword(text):
        return None
    try:
        when = datetime.fromisoformat(record["createdAt"].replace("Z", "+00:00"))
        if when.tzinfo is None or not cutoff <= when.timestamp() <= now:
            return None
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
        return None
    did, rkey = event.get("did"), event.get("rkey")
    if (
        not isinstance(did, str)
        or not did.startswith("did:")
        or not isinstance(rkey, str)
        or not rkey
    ):
        return None
    return {
        "source": "Bluesky Jetstream",
        "kind": "social",
        "author": did,
        "url": f"https://bsky.app/profile/{quote(did, safe=':')}/post/{quote(rkey, safe='')}",
        "published_at": when.astimezone(timezone.utc).isoformat(),
        "title": " ".join(text.splitlines())[:180],
        "text": text,
        "matched_ticker": None,
        "uri": f"at://{did}/app.bsky.feed.post/{rkey}",
    }


class Jetstream:
    def __init__(self, endpoint: str = ENDPOINT, *, cursor: int | None = None):
        self.endpoint = endpoint
        self.cursor = cursor

    async def batches(
        self,
        *,
        batch_seconds: float = 5.0,
        max_age_seconds: float = 21600,
        keyword: Callable[[str], bool] = TERMS.search,
    ) -> AsyncIterator[dict]:
        """Emit heartbeats and immediately flush qualifying posts. Persist cursor after ingest."""
        delay = 1.0
        while True:
            query = {"collections": "app.bsky.feed.post", "kinds": "commit"}
            if self.cursor is not None:
                query["cursor"] = str(self.cursor)
            uri = f"{self.endpoint}?{urlencode(query)}"
            scanned = 0
            try:
                async with connect(
                    uri, subprotocols=["xrpc.v1.json"], open_timeout=12, close_timeout=3
                ) as socket:
                    deadline = monotonic() + max(0.1, batch_seconds)
                    while True:
                        try:
                            frame = await asyncio.wait_for(
                                socket.recv(), max(0.001, deadline - monotonic())
                            )
                        except TimeoutError:
                            frame = None
                        item = None
                        if frame is not None:
                            envelope = json.loads(frame)
                            if envelope.get("$type") != "message":
                                # Error frames must surface instead of falsely reporting the source healthy.
                                raise ValueError(
                                    f"unexpected Jetstream envelope {str(envelope.get('$type'))[:50]}"
                                )
                            event = envelope.get("payload") or {}
                            if event.get("$type", "").endswith("#info") and event.get(
                                "name"
                            ) in {"FutureCursor", "OutdatedCursor"}:
                                self.cursor = None
                                yield {
                                    "items": [],
                                    "scanned": scanned,
                                    "cursor": None,
                                    "state": "degraded",
                                    "error": f"Jetstream {event['name']}: resuming at available position",
                                }
                                scanned = 0
                            seq = event.get("seq")
                            if isinstance(seq, int) and (
                                self.cursor is None or seq > self.cursor
                            ):
                                now = time()
                                item = normalize_post(
                                    event, now - max_age_seconds, now, keyword
                                )
                                self.cursor = seq
                                scanned += 1
                                delay = 1.0
                        if item or monotonic() >= deadline:
                            yield {
                                "items": [item] if item else [],
                                "scanned": scanned,
                                "cursor": self.cursor,
                                "state": "online",
                                "error": "",
                            }
                            scanned = 0
                            deadline = monotonic() + max(0.1, batch_seconds)
            except (OSError, TimeoutError, WebSocketException, ValueError) as error:
                if (
                    isinstance(error, InvalidStatus)
                    and error.response.status_code == 400
                ):
                    try:
                        reason = json.loads(error.response.body).get("error")
                    except (ValueError, AttributeError, TypeError):
                        reason = None
                    if reason == "CursorTooOld":
                        self.cursor = None
                        error = ValueError(
                            "stored cursor expired; resuming from the live tip"
                        )
                yield {
                    "items": [],
                    "scanned": scanned,
                    "cursor": self.cursor,
                    "state": "degraded",
                    "error": f"Jetstream {type(error).__name__}: {str(error)[:100]}",
                    "retry_after": delay,
                }
            await asyncio.sleep(delay)
            delay = min(90, delay * 2)
