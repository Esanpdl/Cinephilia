"""Check Phase 7 using authentic supplied lists; no invented movie/source rows."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from apps.cinematography.services.source_lists import (
    SOURCES, SourceError, deduplicate, load_source, matching_title, safe_pair, title_key,
    fuzzy_title_agrees, validate_unique_source_matches,
)


class SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = [load_source(ROOT / "data/raw/technique_sources" / f"{source}.json") for source in SOURCES]
        cls.entries = [entry for source in cls.sources for entry in source.entries]
        cls.groups = deduplicate(cls.entries)

    def test_complete_sources_have_distinct_ranks(self):
        for source in self.sources:
            self.assertEqual([entry["rank"] for entry in source.entries], list(range(1, 1001)))

    def test_no_citation_is_lost_or_duplicated(self):
        keys = [entry["key"] for group in self.groups for entry in group]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(set(keys), {entry["key"] for entry in self.entries})

    def test_godfather_sources_merge_preserving_original_annotation(self):
        group = next(group for group in self.groups if any(entry["key"] == "letterboxd_top1000:1" for entry in group))
        self.assertEqual(len(group), 2)
        self.assertEqual(group[0]["title"], "The Godfather (1972)")
        self.assertEqual(matching_title(group[0]), "The Godfather")

    def test_remakes_are_not_merged(self):
        scarfaces = [entry for entry in self.entries if title_key(entry["match_title"]) == "scarface"]
        self.assertGreater(len({entry["year"] for entry in scarfaces}), 1)
        for left in scarfaces:
            for right in scarfaces:
                if left["year"] != right["year"]:
                    self.assertFalse(safe_pair(left, right))

    def test_fuzzy_spelling_pair_is_merged(self):
        group = next(group for group in self.groups if any(entry["key"] == "letterboxd_top1000:459" for entry in group))
        self.assertEqual({entry["match_title"] for entry in group}, {"My Neighbor Totoro", "MY NEIGHBOUR TOTORO"})

    def test_same_source_entries_never_merge_by_title(self):
        self.assertTrue(all(len({entry["source"] for entry in group}) == len(group) for group in self.groups))

    def test_sequel_numerals_block_fuzzy_tmdb_match(self):
        self.assertFalse(fuzzy_title_agrees("IVAN THE TERRIBLE, PART II", "Ivan the Terrible, Part I"))
        self.assertTrue(fuzzy_title_agrees("MY NEIGHBOUR TOTORO", "My Neighbor Totoro"))

    def test_same_source_tmdb_collision_blocks_import(self):
        entries = [entry for entry in self.entries if entry["key"] in {"tspdt_top1000:246", "tspdt_top1000:250"}]
        with self.assertRaises(SourceError):
            validate_unique_source_matches(entries, {entry["key"]: {"status": "resolved", "tmdb_id": 9797} for entry in entries})

    def test_year_range_remains_missing(self):
        entry = next(entry for entry in self.entries if entry["key"] == "tspdt_top1000:140")
        self.assertIsNone(entry["year"])

    def assert_invalid(self, mutate):
        # Negative protocol tests mutate copies of real input, never film facts in DB.
        payload = copy.deepcopy(self.sources[0].payload)
        mutate(payload)
        with tempfile.TemporaryDirectory(dir=ROOT / "data/phase7") as folder:
            path = Path(folder) / "invalid.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(SourceError):
                load_source(path)

    def test_duplicate_rank_rejected(self):
        self.assert_invalid(lambda payload: payload["items"][1].update(rank=1))

    def test_incomplete_and_count_mismatch_rejected(self):
        self.assert_invalid(lambda payload: payload.update(complete=False))
        self.assert_invalid(lambda payload: payload.update(actual_count=999))

    def test_non_source_url_rejected(self):
        self.assert_invalid(lambda payload: payload["items"][0].update(source_page_url="https://example.com/"))

    def test_boolean_year_is_not_an_integer_year(self):
        self.assert_invalid(lambda payload: payload["items"][0].update(year=True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
