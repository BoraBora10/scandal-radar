"""Compile replay snapshots used by both transport modes."""
import json
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

from alerts import should_alert
from classifier import classify
from entities import COMPANIES, match_company
from ingestion.demo import INITIAL_FRAME, SOURCES, TAPE
from verifier import verification

ROOT = Path(__file__).resolve().parents[1]
LATENCIES = [3, 4, 5, 2, 4, 3, 2, 4, 2, 3, 2, 3, 3, 2]
PRICES = {
    "HLVD": [74.20, 74.18, 74.25, 74.12, 74.17, 73.94, 74.01, 73.81, 73.65, 73.73, 73.32, 73.41],
    "TVG.D": [48.3, 48.29, 48.31, 48.24, 48.19, 48.13, 48.16],
    "KSN.D": [82.16, 82.2, 82.21, 82.09, 82.1],
}


def compile_demo(levels: set[str] | None = None) -> dict:
    levels = {"verified", "developing"} if levels is None else levels
    feed, logs, alerts, snapshots = [], [], [], []
    signals: dict[str, dict] = {}
    scanned = 0
    for i, (at, source, publisher, ticker, title, text, kind, trusted, count) in enumerate(TAPE):
        company = next(c for c in COMPANIES if c.ticker == ticker)
        match, confidence = classify(text, match_company(text))
        signal = signals.get(ticker)
        filing = kind == "filing" and signal is not None
        item = dict(id=i, at=at, published=at - LATENCIES[i], source=source, publisher=publisher,
                    title=title, text=text, kind=kind, trusted=trusted, matched=match or filing,
                    confidence=confidence, **asdict(company))
        prior = signal["level"] if signal else None
        if match or filing:
            if signal is None:
                signal = signals[ticker] = dict(**asdict(company), first=at, evidence=[])
            signal["evidence"].append(i)
            sources = [feed[j] for j in signal["evidence"][:-1]] + [item]
            signal["level"] = verification(sources)
            # A filing corroborates the departure only. It never establishes a relationship.
            if match:
                signal.update(title=title, text=text, confidence=confidence, latest=i)
            signal["prices"] = PRICES[ticker][:min(len(PRICES[ticker]), 2 + len(sources) * 3)]
            item["level"] = signal["level"]
            if should_alert(prior, signal["level"], levels):
                alerts.append(dict(id=i, at=at, ticker=ticker, title=title, level=signal["level"],
                                   update=prior is not None, latency=LATENCIES[i]))
        else:
            item["level"] = "dismissed"
        scanned += count
        feed.append(item)
        logs.append(dict(at=at, source=SOURCES[source][0], count=count, matched=item["matched"],
                         message="Departure filing linked" if filing else "Subject matched" if match else "No qualifying match"))
        snapshots.append(deepcopy(dict(at=at, items=feed, signals=signals, alerts=alerts,
                                       logs=logs, scanned=scanned, batch=count)))
    return dict(initial=INITIAL_FRAME, frames=snapshots, sources=SOURCES)


if __name__ == "__main__":
    (ROOT / "dashboard" / "replay.json").write_text(json.dumps(compile_demo(), separators=(",", ":")))
