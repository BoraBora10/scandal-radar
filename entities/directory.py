import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from entities.matching import CompanyIndex

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".data" / "directory.json"
SEED = ROOT / "entities" / "seed.json"
OVERRIDES = ROOT / "entities" / "overrides.json"


def apply_overrides(
    data: dict[str, Any], overrides: dict, today: date | None = None
) -> dict:
    today = today or datetime.now(timezone.utc).date()
    companies = []
    for item in data["companies"]:
        override = overrides.get(item["ticker"], {})
        if override.get("valid_until") and today >= date.fromisoformat(
            override["valid_until"]
        ):
            expired = {(p["name"], p.get("source")) for p in override.get("ceos", [])}
            companies.append(
                {
                    **item,
                    "ceos": [
                        p
                        for p in item["ceos"]
                        if (p["name"], p.get("source")) not in expired
                    ],
                }
            )
            continue
        current = {p["name"] for p in item.get("ceos", [])}
        if current and (
            override.get("only_if_unresolved")
            or (
                "replaces_names" in override
                and current != set(override["replaces_names"])
            )
        ):
            companies.append(item)
            continue
        row = {
            **item,
            **{k: v for k, v in override.items() if k in ("company_aliases", "ceos")},
        }
        if "ceos" in override:
            row["ceos"] = [
                {**p, "source": p.get("source", "Manual override")} for p in row["ceos"]
            ]
        companies.append(row)
    return {**data, "companies": companies}


class Directory:
    def __init__(self) -> None:
        try:
            data = json.loads(CACHE.read_text())
        except (OSError, ValueError):
            data = json.loads(SEED.read_text())
        self.install(data)
        self.error = ""

    def install(self, data: dict) -> None:
        override_path = Path(os.getenv("CEO_OVERRIDES_FILE", OVERRIDES))
        directory = apply_overrides(
            data,
            json.loads(override_path.read_text()) if override_path.exists() else {},
        )
        self.index = CompanyIndex(directory["companies"])
        self.data = directory
        self.summary = {
            "as_of": directory["fetched_at"],
            "securities": len(directory["companies"]),
            "issuers": len({r["cik"] for r in directory["companies"]}),
            "covered": sum(bool(r.get("ceos")) for r in directory["companies"]),
            "source": directory["universe_source"],
        }
        self.error = ""
