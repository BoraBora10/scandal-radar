"""Refresh the free constituent/CEO reference directory. Requires beautifulsoup4 and mwparserfromhell."""

from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from collections import defaultdict
from collections.abc import Iterator, Sequence
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlencode, urlsplit
from urllib.request import Request, urlopen

import mwparserfromhell
from bs4 import BeautifulSoup

INDEX_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
WIKI_API = "https://en.wikipedia.org/w/api.php"
DATA_API = "https://www.wikidata.org/w/api.php"
QUERY_API = "https://query.wikidata.org/sparql"
CEO_ROLE = re.compile(r"\b(?:co[ -]?)?(?:CEOs?|chief executive officers?)\b", re.I)


def get(url: str, params: dict[str, str] | None = None) -> bytes:
    if params:
        url += "?" + urlencode(params)
    req = Request(
        url,
        headers={
            "User-Agent": os.getenv(
                "DIRECTORY_USER_AGENT",
                "ScandalRadar/0.2 (daily public reference directory; Python urllib)",
            )
        },
    )
    for attempt in range(3):
        try:
            with urlopen(req, timeout=35) as response:
                return response.read()
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
            retry_after = exc.headers.get("Retry-After", "")
            if retry_after.isdigit() and int(retry_after) > 60:
                raise
            time.sleep(
                int(retry_after) if retry_after.isdigit() else 2 ** (attempt + 1)
            )
        except (TimeoutError, URLError):
            if attempt == 2:
                raise
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError("request did not complete")


def query(url: str, params: dict[str, str]) -> dict:
    payload = json.loads(get(url, {**params, "format": "json"}))
    if "error" in payload:
        raise ValueError(str(payload["error"].get("code", "MediaWiki error")))
    return payload


def batches(values: Sequence[str], n: int) -> Iterator[Sequence[str]]:
    for i in range(0, len(values), n):
        yield values[i : i + n]


def read_index(raw: bytes) -> tuple[list[dict], str | None, str | None]:
    soup = BeautifulSoup(raw, "html.parser")
    table = soup.select_one("table#constituents")
    if not table:
        raise ValueError("Missing S&P 500 constituent table")
    headers = [h.get_text(" ", strip=True) for h in table.tr.find_all("th")]
    columns = {
        k: headers.index(k) for k in ("Symbol", "Security", "GICS Sector", "CIK")
    }
    rows = []
    for tr in table.select("tr")[1:]:
        cells = tr.find_all("td", recursive=False)
        if not cells:
            continue

        def value(key: str) -> str:
            return cells[columns[key]].get_text(" ", strip=True)

        ticker, cik = value("Symbol"), value("CIK")
        if not re.fullmatch(r"[A-Z0-9.\-]{1,12}", ticker) or not re.fullmatch(
            r"\d{1,10}", cik
        ):
            raise ValueError(f"Invalid company identifier in row {ticker!r}")
        link = cells[columns["Security"]].find("a", href=True)
        page = link.get("title") if link else None
        if link and not page:
            page = unquote(
                urlsplit(link["href"]).path.rsplit("/", 1)[-1].removeprefix("./")
            ).replace("_", " ")
        company = value("Security")
        # Strip the share class description. Google and Fox use multiple symbols for one company.
        common = re.sub(r"\s*\(class [^)]+\)\s*$", "", company, flags=re.I)
        rows.append(
            {
                "ticker": ticker,
                "company": company,
                "cik": cik.zfill(10),
                "sector": value("GICS Sector"),
                "company_aliases": [common] if common != company else [],
                "ceos": [],
                "source": INDEX_URL,
                "_page": page,
            }
        )
    if not 475 <= len(rows) <= 550 or len({r["ticker"] for r in rows}) != len(rows):
        raise ValueError(
            f"Unexpected constituent count or duplicate symbols: {len(rows)}"
        )
    meta = soup.find("script", type="application/ld+json")
    page_meta = json.loads(meta.string) if meta and meta.string else {}
    revision = re.search(rb'"wgRevisionId"\s*:\s*(\d+)', raw)
    return (
        rows,
        page_meta.get("dateModified"),
        revision.group(1).decode() if revision else None,
    )


def role_entries(wikitext: str) -> list[str]:
    """Extract names only when the infobox explicitly attaches a CEO role to a name."""
    clean = re.sub(
        r"<!--.*?-->|<ref\b[^>]*?/>|<ref\b[^>]*>.*?</ref\s*>",
        " ",
        wikitext,
        flags=re.I | re.S,
    )
    code = mwparserfromhell.parse(clean)
    info = next(
        (
            t
            for t in code.filter_templates(recursive=False)
            if str(t.name).strip().lower().startswith("infobox")
        ),
        None,
    )
    if not info:
        return []
    param = next(
        (
            p
            for p in info.params
            if re.sub(r"[ _]", "", str(p.name).lower()) == "keypeople"
        ),
        None,
    )
    if not param:
        return []
    raw = str(param.value)
    for link in mwparserfromhell.parse(raw).filter_wikilinks():
        raw = raw.replace(str(link), str(link.text or link.title))
    raw = re.sub(r"<br\s*/?\s*>|<li\b[^>]*>|</li>|\n\s*[*#]", "\n", raw, flags=re.I)
    # Preserve list entries, including split name/role entries in {{ubl|Name|(CEO)}}.
    raw = re.sub(
        r"\{\{\s*(?:unbulleted list|ubli?|idp|indented plainlist|plainlist|flatlist|hlist|nowrap|nobreak|small|smaller)\s*\|",
        "|",
        raw,
        flags=re.I,
    )
    raw = re.sub(r"\{\{[^{}]+\}\}", "", raw)
    raw = (
        BeautifulSoup(raw.replace("}}", ""), "html.parser")
        .get_text()
        .replace("'''", "")
        .replace("''", "")
    )
    parts = [
        " ".join(s.strip(" *;,").split())
        for s in re.split(r"[\n|;]", raw)
        if s.strip(" *;,")
    ]
    names = []
    for i, part in enumerate(parts):
        hit = CEO_ROLE.search(part)
        if not hit or re.search(
            r"\b(?:former|retired|designate|incoming|subsidiary)\b|\bCEO\s+of\b",
            part,
            re.I,
        ):
            continue
        # A division head can appear next to the corporate CEO in the same infobox.
        scoped = re.match(r"\s*[,/:]\s*([^)]*)", part[hit.end() :])
        if scoped and not re.match(
            r"(?:chair|president|founder|director|chief\b|CFO\b|COO\b|executive chair)",
            scoped[1],
            re.I,
        ):
            continue
        # Drop the role group. Titles can be parenthesized or separated by a comma or en dash.
        prefix = part[: hit.start()].strip()
        # Handle a flat list such as "Name A, Chairman, Name B, CEO".
        pairs = re.split(
            r"\b(?:chairman|chairwoman|chair|director|president|CFO|COO)\s*,\s*(?=[A-Z])",
            prefix,
            flags=re.I,
        )
        if len(pairs) > 1 and len(pairs[-1].strip(" ,").split()) >= 2:
            prefix = pairs[-1]
        if "(" in prefix:
            prefix = prefix.rsplit("(", 1)[0]
        prefix = re.split(
            r",\s*(?=(?:interim |acting |co[- ])?(?:chair|president|CEO|chief|director|founder))|\s+[–—-]\s+",
            prefix,
            flags=re.I,
        )[0]
        prefix = re.sub(
            r"\b(?:chief executive officer|executive chair(?:man|woman|person)?|chair(?:man|woman|person)?|president|co-founder|founder|interim|acting|co-)\b.*$",
            "",
            prefix,
            flags=re.I,
        )
        prefix = prefix.strip(" ()\t-,–—&")
        if not prefix or prefix.lower() in ("and", "the"):
            prefix = parts[i - 1] if i else ""
        proposals = re.split(r"\s+(?:and|&)\s+", prefix)
        for name in proposals:
            name = name.strip(" (),–—&:").replace("\xa0", " ")
            tokens = name.split()
            if (
                2 <= len(tokens) <= 6
                and all(
                    (
                        t[:1].isupper()
                        or t
                        in ("de", "da", "van", "von", "del", "bin", "den", "al", "la")
                    )
                    and all(c.isalpha() or c in ".-’'‐" for c in t)
                    for t in tokens
                )
                and not re.search(
                    r"\b(?:CEO|CFO|COO|Chairman|President|Board|Chief|Executive|Officer|Director|Founder|Co-Chair|Chair|Treasurer|General|Chairwoman)\b",
                    name,
                    re.I,
                )
            ):
                names.append(name)
    return list(dict.fromkeys(names))


def wiki_pages(titles: list[str]) -> dict[str, dict]:
    result = {}
    for group in batches(sorted(set(titles)), 25):
        data = query(
            WIKI_API,
            {
                "action": "query",
                "titles": "|".join(group),
                "redirects": "1",
                "formatversion": "2",
                "prop": "pageprops|revisions",
                "ppprop": "wikibase_item",
                "rvprop": "content|timestamp|ids",
                "rvslots": "main",
                "rvsection": "0",
                "maxlag": "5",
            },
        )["query"]
        redirects = {
            r["from"]: r["to"]
            for k in ("normalized", "redirects")
            for r in data.get(k, [])
        }
        fragments = {
            r["from"] for r in data.get("redirects", []) if r.get("tofragment")
        }
        index = {p["title"]: p for p in data["pages"]}
        for title in group:
            if title in fragments:
                continue
            key = title
            for _ in range(6):
                if key not in redirects:
                    break
                key = redirects[key]
            page = index.get(key, {})
            rev = next(iter(page.get("revisions", [])), {})
            if rev:
                result[title] = {
                    "qid": page.get("pageprops", {}).get("wikibase_item"),
                    "names": role_entries(rev["slots"]["main"].get("content", "")),
                    "source": "https://en.wikipedia.org/w/index.php?oldid="
                    + str(rev["revid"]),
                    "updated": rev.get("timestamp"),
                    "title": key,
                }
        time.sleep(0.25)
    return result


def wikidata_people(company_ids: list[str], today: date) -> dict[str, list[dict]]:
    """Look up qualified, nondeprecated P169 statements and English name variants."""
    candidates: dict[str, dict[str, bool]] = defaultdict(dict)
    for group in batches(sorted(set(company_ids)), 50):
        ids = " ".join("wd:" + q for q in group if re.fullmatch(r"Q\d+", q))
        sparql = f"""
SELECT DISTINCT ?company ?person ?rank ?start ?end WHERE {{
  VALUES ?company {{ {ids} }}
  ?company p:P169 ?stmt.
  ?stmt ps:P169 ?person; wikibase:rank ?rank.
  ?person wdt:P31 wd:Q5.
  FILTER (?rank != wikibase:DeprecatedRank)
  FILTER NOT EXISTS {{ ?person wdt:P570 ?death }}
  OPTIONAL {{ ?stmt pq:P580 ?start }}
  OPTIONAL {{ ?stmt pq:P582 ?end }}
}}
"""
        for row in query(QUERY_API, {"query": sparql})["results"]["bindings"]:
            start = row.get("start", {}).get("value", "")[:10]
            end = row.get("end", {}).get("value", "")[:10]
            if (start and start > today.isoformat()) or (
                end and end <= today.isoformat()
            ):
                continue
            company = row["company"]["value"].split("/")[-1]
            person = row["person"]["value"].split("/")[-1]
            candidates[company][person] = candidates[company].get(person, False) or row[
                "rank"
            ]["value"].endswith("PreferredRank")
        time.sleep(0.25)
    ids = sorted({i for people in candidates.values() for i in people})
    labels = {}
    for group in batches(ids, 50):
        data = query(
            DATA_API,
            {
                "action": "wbgetentities",
                "ids": "|".join(group),
                "props": "labels|aliases",
                "languages": "en",
                "maxlag": "5",
            },
        )["entities"]
        for qid, entity in data.items():
            name = entity.get("labels", {}).get("en", {}).get("value")
            if name:
                labels[qid] = {
                    "name": name,
                    "aliases": [
                        a["value"]
                        for a in entity.get("aliases", {}).get("en", [])
                        if len(a["value"].split()) >= 2
                    ],
                    "qid": qid,
                }
        time.sleep(0.25)
    return {
        company: [
            {
                **labels[p],
                "preferred": pref,
                "source": f"https://www.wikidata.org/wiki/{company}#P169",
            }
            for p, pref in people.items()
            if p in labels
        ]
        for company, people in candidates.items()
    }


def name_key(name: str) -> tuple[str, str]:
    n = unicodedata.normalize("NFKD", name.lower())
    tokens = re.findall(
        r"[^\W\d_]+", "".join(c for c in n if not unicodedata.combining(c))
    )
    tokens = [t for t in tokens if t not in {"jr", "sr", "ii", "iii", "iv"}]
    return (tokens[0], tokens[-1]) if len(tokens) >= 2 else ("", "")


def refresh_directory() -> dict:
    rows, updated, revision = read_index(get(INDEX_URL))
    pages = wiki_pages([r["_page"] for r in rows if r["_page"]])
    # A spinoff may redirect to its former parent's page. Never share that parent's officers.
    issuers_by_page = defaultdict(set)
    for row in rows:
        resolved = pages.get(row["_page"], {}).get("title")
        if resolved:
            issuers_by_page[resolved].add(row["cik"])
    pages = {
        title: page
        for title, page in pages.items()
        if page["title"] == title or len(issuers_by_page[page["title"]]) == 1
    }
    today = datetime.now(timezone.utc).date()
    by_ceo = wikidata_people([p["qid"] for p in pages.values() if p["qid"]], today)
    for row in rows:
        title = row.pop("_page")
        page = pages.get(title, {})
        wiki_names = page.get("names", [])
        candidates = by_ceo.get(page.get("qid"), [])
        if page:
            alias = re.sub(r"\s*\([^)]*\)\s*$", "", page["title"])
            if alias != row["company"] and alias not in row["company_aliases"]:
                row["company_aliases"].append(alias)
        if wiki_names:
            for name in wiki_names:
                matches = [
                    p
                    for p in candidates
                    if any(
                        name_key(alt) == name_key(name)
                        for alt in [p["name"], *p["aliases"]]
                    )
                ]
                variants = {
                    n
                    for person in matches
                    for n in [person["name"], *person["aliases"]]
                }
                row["ceos"].append(
                    {
                        "name": name,
                        "aliases": sorted(variants - {name}),
                        "source": page["source"],
                    }
                )
        else:
            preferred = [p for p in candidates if p["preferred"]]
            usable = preferred or candidates
            # Multiple explicitly preferred open claims may be co-CEOs. If rank gives no signal
            # and the infobox does not identify the holders, keep the conflict unresolved.
            if len(usable) == 1 or preferred:
                row["ceos"] = [
                    {k: p[k] for k in ("name", "aliases", "source")} for p in usable
                ]
        for person in row["ceos"]:
            spelling = re.sub(r"(?<=\s)[A-Z]\.?\s+(?=\S)", "", person["name"])
            if spelling != person["name"] and len(spelling.split()) >= 2:
                person["aliases"] = sorted(set(person["aliases"]) | {spelling})
        if revision:
            row["source"] = "https://en.wikipedia.org/w/index.php?oldid=" + revision
    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "universe_source": INDEX_URL,
        "universe_revision": revision,
        "universe_modified": updated,
        "companies": rows,
    }


def write_directory(target: Path) -> dict:
    result = refresh_directory()
    target.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", dir=target.parent, encoding="utf-8", delete=False
    ) as out:
        json.dump(result, out, ensure_ascii=False, separators=(",", ":"))
        out.write("\n")
        temp = Path(out.name)
    temp.replace(target)
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    data = write_directory(parser.parse_args().output)
    print(
        f"{len(data['companies'])} securities, {sum(bool(c['ceos']) for c in data['companies'])} with a sourced CEO."
    )
