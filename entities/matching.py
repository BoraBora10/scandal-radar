"""Index issuer aliases and require an executive and issuer in the same story."""

import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass

from rapidfuzz.fuzz import ratio


def words(value: str) -> str:
    chars = unicodedata.normalize("NFKD", value.casefold())
    return " ".join(
        re.findall(
            r"[a-z0-9]+", "".join(c for c in chars if not unicodedata.combining(c))
        )
    )


COMMON = {
    "smith",
    "johnson",
    "brown",
    "jones",
    "williams",
    "lee",
    "wang",
    "chen",
    "miller",
    "davis",
    "wilson",
    "martin",
    "moore",
    "white",
    "clark",
    "young",
}
SUFFIX = re.compile(
    r"\s+(?:(?:incorporated|inc|corporation|corp|company|plc|limited|ltd|holdings|group|class [ab])\s*)+$"
)


@dataclass(frozen=True)
class Match:
    ticker: str
    company: str
    ceo: str


class CompanyIndex:
    def __init__(self, companies: list[dict]) -> None:
        self.companies = companies
        self.aliases = {}
        self.anchor = defaultdict(set)
        self.executives = {}
        self.by_surname = defaultdict(set)
        self.symbols = {}
        self.surnames = Counter()
        for row in companies:
            symbol = row["ticker"]
            aliases = {
                words(value)
                for value in [row["company"], *row.get("company_aliases", [])]
                if value
            }
            aliases.update(SUFFIX.sub("", value).strip() for value in list(aliases))
            aliases = {
                a
                for a in aliases
                if (len(a) >= 3 or (len(a) == 2 and any(c.isdigit() for c in a)))
                and a not in {"the", "inc", "corp", "group", "company", "holdings"}
            }
            self.aliases[symbol] = aliases
            for a in aliases:
                self.anchor[max(a.split(), key=len)].add(symbol)
            self.symbols[symbol] = row
            people = []
            for person in row.get("ceos", []):
                names = {
                    words(n) for n in [person["name"], *person.get("aliases", [])] if n
                }
                names = {n for n in names if len(n.split()) >= 2}
                for n in list(names):
                    parts = n.split()
                    if len(parts) > 2 and all(len(p) == 1 for p in parts[1:-1]):
                        names.add(parts[0] + " " + parts[-1])
                for n in names:
                    self.by_surname[n.split()[-1]].add(symbol)
                people.append((person["name"], names))
                self.surnames[words(person["name"]).split()[-1]] += 1
            self.executives[symbol] = people

    def match(self, text: str) -> Match | None:
        body = words(text)
        tokens = body.split()
        padded = f" {body} "
        symbols = {
            s.upper()
            for s in re.findall(
                r"(?:\$|\b(?:NYSE|NASDAQ)\s*:\s*|\()([A-Z][A-Z0-9.\-]{0,5})\b", text
            )
        }
        symbols.update(
            t
            for t in re.findall(r"\b[A-Z]{3,5}\b", text)
            if t in self.symbols
            and t
            not in {
                "ALL",
                "FOR",
                "ARE",
                "NOW",
                "CEO",
                "CFO",
                "USA",
                "HAS",
                "LOW",
                "KEY",
                "SEE",
                "DAY",
                "IT",
            }
        )
        candidates = {
            s
            for t in set(tokens)
            for s in (*self.anchor.get(t, ()), *self.by_surname.get(t, ()))
        } | (symbols & self.symbols.keys())
        matches = []
        for symbol in sorted(candidates):
            named = any(f" {a} " in padded for a in self.aliases[symbol])
            if not named and symbol not in symbols:
                # A near-spelled issuer needs an exact executive name; avoid matching two fuzzy strings.
                people = self.executives[symbol]
                exact_person = any(
                    f" {n} " in padded
                    for _, names in people
                    for n in names
                    if n.split()[-1] not in COMMON
                )
                if not exact_person:
                    continue
                for alias in self.aliases[symbol]:
                    size = len(alias.split())
                    if len(alias) >= 9 and any(
                        ratio(alias, " ".join(tokens[i : i + size])) >= 94
                        for i in range(len(tokens) - size + 1)
                    ):
                        named = True
                        break
                if not named:
                    continue
            for full, aliases in self.executives[symbol]:
                if not named and (
                    words(full).split()[-1] in COMMON
                    or self.surnames[words(full).split()[-1]] > 1
                ):
                    continue
                found = any(f" {n} " in padded for n in aliases)
                if not found:
                    for n in aliases:
                        parts = n.split()
                        if len(n) < 9:
                            continue
                        size = len(parts)
                        for index in range(len(tokens) - size + 1):
                            window = tokens[index : index + size]
                            if (
                                parts[0] == window[0] or parts[-1] == window[-1]
                            ) and ratio(n, " ".join(window)) >= 92:
                                found = True
                                break
                        if found:
                            break
                if found:
                    matches.append(Match(symbol, self.symbols[symbol]["company"], full))
        # Share classes of the same CIK describe the same issuer.
        identities = {(self.symbols[m.ticker]["cik"], m.ceo) for m in matches}
        return matches[0] if len(identities) == 1 else None
