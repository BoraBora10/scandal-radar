import tempfile
import unittest
from pathlib import Path

from entities.directory import apply_overrides
from entities.matching import CompanyIndex
from ingestion.store import Store
from ingestion.records import canonical

NOW = 1_795_000_000
ROW = {
    "ticker": "EXM.D",
    "company": "Example Meridian Inc.",
    "cik": "0000000001",
    "company_aliases": ["Example Meridian"],
    "ceos": [{"name": "Alison Quell", "aliases": ["Ali Quell"]}],
}
HEADLINE = "Example Meridian CEO Alison Quell addresses an undisclosed relationship in a board statement"


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "events.sqlite")
        self.idx = CompanyIndex([ROW])

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def put(
        self,
        source,
        title=HEADLINE,
        url="https://example.invalid/a",
        when=NOW - 20,
        **extra,
    ):
        row = dict(url=url, title=title, text=title, published_at=when, **extra)
        return self.store.put(source, [row], 1, self.idx, NOW)

    def test_alias_fuzzy_boundaries(self):
        self.assertEqual(
            self.idx.match("Example Meridian CEO Ali Quell").ceo, "Alison Quell"
        )
        self.assertEqual(
            self.idx.match("Example Meridian CEO Alisson Quell").ceo, "Alison Quell"
        )
        self.assertIsNone(self.idx.match("Example Meridianette CEO Alison Quell"))
        self.assertIsNone(self.idx.match("A report about Alison Quell"))

    def test_common_name_needs_company(self):
        idx = CompanyIndex([{**ROW, "ceos": [{"name": "Alan Smith"}]}])
        self.assertIsNone(idx.match("Alan Smith $EXM.D"))
        self.assertIsNotNone(idx.match("Alan Smith at Example Meridian"))

    def test_duplicates_keep_provenance_and_count_one_event(self):
        self.put("pr", url="https://example.invalid/a?utm_source=rss")
        self.assertEqual(self.put("pr"), 0)
        self.put("google", title=HEADLINE + ".", url="https://news.example.invalid/b")
        s = self.store.snapshot([], {}, NOW)
        self.assertEqual(s["counts"], {"candidate": 1})
        self.assertEqual(len(s["records"][0]["evidence"]), 2)
        self.assertEqual(s["records"][0]["matched_ticker"], "EXM.D")

    def test_separate_signals_and_freshness(self):
        self.put("pr")
        self.put(
            "business",
            title="Example Meridian CEO Alison Quell presents third-quarter production figures",
            url="https://example.invalid/c",
        )
        self.assertEqual(
            self.put("pr", when=NOW - 21601, url="https://example.invalid/old"), 0
        )
        self.assertEqual(
            self.put("pr", when=None, url="https://example.invalid/no-date"), 0
        )
        self.assertEqual(
            self.put("pr", when=NOW + 300, url="https://example.invalid/future"), 0
        )
        self.assertEqual(len(self.store.snapshot([], {}, NOW)["records"]), 2)
        self.assertEqual(self.store.snapshot([], {}, NOW + 21601)["records"], [])

    def test_filing_is_never_a_claim(self):
        for k in ("a", "b"):
            self.put(
                "sec",
                title="Example Meridian files Item 5.02",
                url="https://example.invalid/" + k,
                kind="filing",
                matched_ticker=ROW["ticker"],
            )
        s = self.store.snapshot([], {}, NOW)
        self.assertEqual(s["counts"], {"filing": 2})
        self.assertTrue(all(not r["ceo"] for r in s["records"]))

    def test_override_persists_in_directory(self):
        d = apply_overrides(
            {"companies": [ROW]}, {"EXM.D": {"ceos": [{"name": "Nora Kex"}]}}
        )
        self.assertEqual(d["companies"][0]["ceos"][0]["source"], "Manual override")
        self.assertEqual(
            CompanyIndex(d["companies"]).match("Nora Kex, Example Meridian").ticker,
            ROW["ticker"],
        )

    def test_unsafe_source_link_rejected(self):
        self.assertEqual(canonical("javascript:alert(1)"), "")
        self.assertEqual(
            canonical("https://x.invalid/a?id=5&utm_campaign=foo"),
            "https://x.invalid/a?id=5",
        )
