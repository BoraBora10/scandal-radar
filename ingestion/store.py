"""A bounded rolling news store. One writer commits a scan and its telemetry together."""

import sqlite3
import time
from pathlib import Path

from rapidfuzz.fuzz import ratio

from entities.matching import CompanyIndex, words
from ingestion.records import RELATIONSHIP, canonical, epoch, key, plain


class Store:
    def __init__(self, path: Path, max_age: int = 21600):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.max_age = max_age
        self.db.executescript("""
          PRAGMA journal_mode=WAL;
          CREATE TABLE IF NOT EXISTS evidence (
            id TEXT PRIMARY KEY, event TEXT NOT NULL, source TEXT, publisher TEXT,
            title TEXT, norm TEXT, text TEXT, url TEXT, author TEXT, published_at INTEGER,
            detected_at INTEGER, ticker TEXT, company TEXT, ceo TEXT, kind TEXT, basis TEXT);
          CREATE INDEX IF NOT EXISTS news_time ON evidence(published_at DESC);
          CREATE INDEX IF NOT EXISTS news_event ON evidence(event);
          CREATE INDEX IF NOT EXISTS news_title ON evidence(norm);
          CREATE TABLE IF NOT EXISTS scans(at INTEGER, source TEXT, scanned INTEGER, added INTEGER);
          CREATE INDEX IF NOT EXISTS scans_time ON scans(at);
          CREATE TABLE IF NOT EXISTS cursor (source TEXT PRIMARY KEY, value TEXT);
        """)

    def put(
        self,
        source: str,
        items: list[dict],
        scanned: int,
        index: CompanyIndex,
        now: int | None = None,
        cursor: str | None = None,
    ) -> int:
        now = int(time.time()) if now is None else now
        cutoff = now - self.max_age
        added = 0
        with self.db:
            for it in items:
                published, url = (
                    epoch(it.get("published_at")),
                    canonical(it.get("url", "")),
                )
                title, text = plain(it.get("title", ""), 320), plain(it.get("text", ""))
                if (
                    not url
                    or published is None
                    or not cutoff <= published <= now + 120
                    or not title
                ):
                    continue
                rid = key(source + "|" + url)
                if self.db.execute(
                    "SELECT 1 FROM evidence WHERE id=?", (rid,)
                ).fetchone():
                    continue
                filing = it.get("kind") == "filing" and source == "sec"
                ticker, company, ceo = "", "", ""
                kind = "wire"
                if filing:
                    ticker = it.get("matched_ticker", "")
                    if ticker not in index.symbols:
                        continue
                    company, kind = index.symbols[ticker]["company"], "filing"
                elif RELATIONSHIP.search(title + " " + text):
                    match = index.match(title + " " + text)
                    if match:
                        ticker, company, ceo, kind = (
                            match.ticker,
                            match.company,
                            match.ceo,
                            "candidate",
                        )
                if source == "bluesky" and not ticker:
                    continue
                publisher = plain(
                    it.get("publisher") or it.get("author") or source, 120
                )
                norm = words(title.removesuffix(" - " + publisher))
                prior = self.db.execute(
                    "SELECT event FROM evidence WHERE (url=? OR (norm=? AND kind!='filing' AND ?!='filing')) AND published_at>=? ORDER BY detected_at LIMIT 1",
                    (url, norm, kind, cutoff),
                ).fetchone()
                event = prior["event"] if prior else rid
                if prior is None and kind != "filing":
                    # Compare near-identical syndications within this issuer/window. Keep every source record.
                    rows = self.db.execute(
                        "SELECT norm,event FROM evidence WHERE ticker=? AND kind=? AND published_at BETWEEN ? AND ? ORDER BY published_at DESC LIMIT 250",
                        (ticker, kind, max(cutoff, published - 7200), published + 7200),
                    )
                    for row in rows:
                        if len(norm) > 25 and ratio(norm, row["norm"]) >= 93:
                            event = row["event"]
                            break
                self.db.execute(
                    "INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        rid,
                        event,
                        source,
                        publisher,
                        title,
                        norm,
                        text,
                        url,
                        plain(it.get("author", ""), 120),
                        published,
                        now,
                        ticker,
                        company,
                        ceo,
                        kind,
                        it.get("time_basis", "published"),
                    ),
                )
                added += 1
            self.db.execute(
                "INSERT INTO scans VALUES(?,?,?,?)", (now, source, scanned, added)
            )
            if cursor is not None:
                self.db.execute(
                    "INSERT OR REPLACE INTO cursor VALUES(?,?)", (source, cursor)
                )
            self.db.execute("DELETE FROM evidence WHERE published_at<?", (cutoff,))
            self.db.execute("DELETE FROM scans WHERE at<?", (now - 86400,))
        return added

    def refresh_matches(self, index: CompanyIndex) -> None:
        with self.db:
            for row in self.db.execute(
                "SELECT id,source,title,text,kind FROM evidence WHERE kind!='filing'"
            ).fetchall():
                text = row["title"] + " " + row["text"]
                match = index.match(text) if RELATIONSHIP.search(text) else None
                if row["source"] == "bluesky" and match is None:
                    self.db.execute("DELETE FROM evidence WHERE id=?", (row["id"],))
                    continue
                self.db.execute(
                    "UPDATE evidence SET ticker=?,company=?,ceo=?,kind=? WHERE id=?",
                    (
                        match.ticker if match else "",
                        match.company if match else "",
                        match.ceo if match else "",
                        "candidate" if match else "wire",
                        row["id"],
                    ),
                )

    def cursor(self, source: str) -> str | None:
        row = self.db.execute(
            "SELECT value FROM cursor WHERE source=?", (source,)
        ).fetchone()
        return row[0] if row else None

    def snapshot(
        self, statuses: list[dict], directory: dict, now: int | None = None
    ) -> dict:
        now = int(time.time()) if now is None else now
        cutoff = now - self.max_age
        # Distinct query per desk function keeps important filings and candidates visible in a busy wire.
        events = {}
        for clause, limit in [
            ("1", 75),
            ("kind='candidate'", 80),
            ("kind='filing'", 80),
        ]:
            grouped = self.db.execute(
                f"SELECT event, MAX(published_at) AS latest FROM evidence WHERE published_at>=? AND {clause} GROUP BY event ORDER BY latest DESC LIMIT ?",
                (cutoff, limit),
            )
            for row in grouped:
                if row["event"] in events:
                    continue
                evidence = [
                    dict(r)
                    for r in self.db.execute(
                        "SELECT * FROM evidence WHERE event=? AND published_at>=? ORDER BY published_at DESC, id LIMIT 16",
                        (row["event"], cutoff),
                    )
                ]
                entry = next((r for r in evidence if r["kind"] != "wire"), evidence[0])
                events[row["event"]] = {
                    **entry,
                    "matched_ticker": entry["ticker"] or None,
                    "id": row["event"],
                    "evidence": [
                        {
                            k: r[k]
                            for k in (
                                "source",
                                "publisher",
                                "url",
                                "author",
                                "published_at",
                                "basis",
                            )
                        }
                        for r in evidence
                    ],
                }
        records = sorted(events.values(), key=lambda r: r["published_at"], reverse=True)
        start_day = now - now % 86400
        summary = self.db.execute(
            "SELECT coalesce(sum(scanned),0),coalesce(sum(added),0) FROM scans WHERE at>=?",
            (start_day,),
        ).fetchone()
        start = now - now % 60 - 59 * 60
        bins = [0] * 60
        for row in self.db.execute(
            "SELECT (at-?)/60 AS slot,sum(scanned) FROM scans WHERE at BETWEEN ? AND ? GROUP BY slot",
            (start, start, now),
        ):
            bins[int(row[0])] = row[1]
        counts = dict(
            self.db.execute(
                "SELECT kind,count(DISTINCT event) FROM evidence WHERE published_at>=? GROUP BY kind",
                (cutoff,),
            )
        )
        step = max(60, self.max_age // 36)
        last_bin = now - now % step
        first_bin = last_bin - 35 * step
        frequency = [0] * 36
        for bucket, total in self.db.execute(
            "SELECT (published_at-?)/? AS b,count(DISTINCT event) FROM evidence WHERE published_at BETWEEN ? AND ? GROUP BY b",
            (first_bin, step, max(cutoff, first_bin), now),
        ):
            frequency[int(bucket)] = total
        return dict(
            publications=frequency,
            publication_start=first_bin,
            publication_step=step,
            as_of=now,
            window_seconds=self.max_age,
            records=records,
            sources=statuses,
            scanned=summary[0],
            added=summary[1],
            counts=counts,
            activity=bins,
            activity_start=start,
            directory=directory,
        )
