"""Regression coverage for topic hierarchy and starter package boundaries."""

from __future__ import annotations

import contextlib
import io
import json
import sqlite3
import sys
import tempfile
import tomllib
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import genanki


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import build_constellation_bundles  # noqa: E402
import build_country_bundles  # noqa: E402
from lib.topic_deck import build_package, load_deck  # noqa: E402


REGIONS = {
    "asia": (1, "アジア"),
    "middle-east": (2, "中東"),
    "europe": (3, "欧州"),
    "africa": (4, "アフリカ"),
    "north-america": (5, "北米"),
    "latin-america": (6, "中南米"),
    "oceania": (7, "大洋州"),
}
SEASONS = {
    "spring": (1, "春"),
    "summer": (3, "夏"),
    "autumn": (5, "秋"),
    "winter": (7, "冬"),
}


def read_config(deck_dir: Path) -> dict:
    with (deck_dir / "deck.toml").open("rb") as handle:
        return tomllib.load(handle)


def config_dirs(root: Path) -> list[Path]:
    return sorted(path.parent for path in root.glob("**/deck.toml"))


def assert_partitioned_fact_ids(
    case: unittest.TestCase,
    groups: dict[str, list[Path]],
    expected_total: int,
) -> dict[str, dict[str, dict[str, str]]]:
    """Check every configured fact appears once in exactly one group."""
    loaded: dict[str, dict[str, dict[str, str]]] = {}
    all_ids: list[str] = []
    for group, deck_dirs in groups.items():
        group_rows: dict[str, dict[str, str]] = {}
        for deck_dir in deck_dirs:
            config, facts, _ = load_deck(deck_dir)
            expected_rows = config.get("validation", {}).get("expected_rows")
            if expected_rows is not None:
                case.assertEqual(len(facts), expected_rows, str(deck_dir.relative_to(ROOT)))
            fact_ids = [row["fact_id"] for row in facts]
            case.assertEqual(len(fact_ids), len(set(fact_ids)), str(deck_dir.relative_to(ROOT)))
            case.assertTrue(all(fact_id.startswith("starter-") for fact_id in fact_ids))
            for row in facts:
                case.assertNotIn(row["fact_id"], group_rows, str(deck_dir.relative_to(ROOT)))
                group_rows[row["fact_id"]] = row
            all_ids.extend(fact_ids)
        loaded[group] = group_rows
    case.assertEqual(len(all_ids), expected_total)
    case.assertEqual(len(all_ids), len(set(all_ids)), "a FactId appears in multiple groups")
    return loaded


def inspect_package(path: Path, temp_root: Path) -> tuple[dict[str, str], list[tuple[str, int, int]], dict[str, dict]]:
    database = temp_root / f"{path.stem}.anki2"
    with zipfile.ZipFile(path) as archive:
        database.write_bytes(archive.read("collection.anki2"))
    with sqlite3.connect(database) as connection:
        notes = {
            guid: fields.split("\x1f")[5]
            for guid, fields in connection.execute("select guid, flds from notes")
        }
        cards = [
            (guid, ordinal, deck_id)
            for guid, ordinal, deck_id in connection.execute(
                "select n.guid, c.ord, c.did from notes n join cards c on c.nid=n.id"
            )
        ]
        decks = json.loads(connection.execute("select decks from col").fetchone()[0])
    return notes, cards, decks


class DeckHierarchyTests(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.temp_root = Path(self.temp.name)

    def test_country_configs_are_regional_shards_with_stable_ids(self):
        country_root = ROOT / "decks/countries"
        country_dirs = config_dirs(country_root)
        self.assertEqual(len(country_dirs), 21)
        self.assertFalse((country_root / "capital/deck.toml").exists())
        self.assertFalse((country_root / "country-name/deck.toml").exists())
        self.assertFalse((country_root / "country-flag/deck.toml").exists())

        expected_groups: dict[str, list[Path]] = {}
        model_ids = {"starter-capitals": 2601020106, "starter-names": 2601020102, "starter-flags": 2601020104}
        id_offsets = {"starter-capitals": 400, "starter-names": 300, "starter-flags": 200}
        for family, direction in (
            ("starter-capitals", "国名→首都"),
            ("starter-names", "首都→国名"),
            ("starter-flags", None),
        ):
            group_dirs = sorted((country_root / family).glob("*/deck.toml"))
            group_dirs = [path.parent for path in group_dirs]
            self.assertEqual(len(group_dirs), 7)
            expected_groups[family] = group_dirs
            for deck_dir in group_dirs:
                region_slug = deck_dir.name
                region_number, region_name = REGIONS[region_slug]
                config = read_config(deck_dir)
                deck = config["deck"]
                expected_name = f"国・地域::国旗::{region_name}" if direction is None else (
                    f"国・地域::首都::{region_name}::{direction}"
                )
                self.assertEqual(deck["name"], expected_name)
                self.assertEqual(deck["id"], 2601020000 + id_offsets[family] + region_number)
                self.assertEqual(deck["model_id"], model_ids[family])
                self.assertEqual(deck.get("fact_id_prefix"), "starter-")
                self.assertFalse(deck.get("include_reverse", False))
                self.assertNotIn("reverse_deck", deck)
                self.assertEqual(len(deck["name"].split("::")), 3 if direction is None else 4)

        loaded = assert_partitioned_fact_ids(self, expected_groups, 588)
        self.assertEqual(len(loaded["starter-capitals"]), 196)
        self.assertEqual(len(loaded["starter-names"]), 196)
        self.assertEqual(len(loaded["starter-flags"]), 196)

    def test_constellation_configs_are_seasonal_shards_with_stable_ids(self):
        constellation_root = ROOT / "decks/constellations"
        self.assertEqual(len(config_dirs(constellation_root)), 12)
        for aggregate in ("name", "main-stars", "visual"):
            self.assertFalse((constellation_root / aggregate / "deck.toml").exists())

        expected_groups: dict[str, list[Path]] = {}
        topic_labels = {
            "starter-name": "星座名",
            "starter-main-stars": "主要恒星",
            "starter-visual": "星図",
        }
        id_bases = {"starter-name": 2601031100, "starter-main-stars": 2601031300, "starter-visual": 2601031200}
        model_ids = {"starter-name": 2601030102, "starter-main-stars": 2601030302, "starter-visual": 2601030202}
        directions = {
            "starter-name": ("日本語名→学名・略号", "学名・略号→日本語名"),
            "starter-main-stars": ("固有名→星座・符号", "星座・符号→固有名"),
            "starter-visual": (None, None),
        }

        for family, topic_label in topic_labels.items():
            group_dirs = sorted((constellation_root / family).glob("*/deck.toml"))
            group_dirs = [path.parent for path in group_dirs]
            self.assertEqual(len(group_dirs), 4)
            expected_groups[family] = group_dirs
            forward, reverse = directions[family]
            for deck_dir in group_dirs:
                season_number, season_name = SEASONS[deck_dir.name]
                config = read_config(deck_dir)
                deck = config["deck"]
                prefix = f"星座・恒星::{topic_label}::{season_name}"
                self.assertEqual(deck["name"], prefix if forward is None else f"{prefix}::{forward}")
                self.assertEqual(deck["id"], id_bases[family] + season_number)
                self.assertEqual(deck["model_id"], model_ids[family])
                self.assertEqual(deck.get("fact_id_prefix"), "starter-")
                self.assertEqual(bool(deck.get("include_reverse", False)), reverse is not None)
                if reverse is None:
                    self.assertNotIn("reverse_deck", deck)
                else:
                    self.assertEqual(deck["reverse_deck"]["id"], deck["id"] + 1)
                    self.assertEqual(deck["reverse_deck"]["name"], f"{prefix}::{reverse}")
                self.assertEqual(len(deck["name"].split("::")), 3 if forward is None else 4)

        loaded = assert_partitioned_fact_ids(self, expected_groups, 203)
        self.assertEqual([len(loaded[k]) for k in topic_labels], [88, 27, 88])

    def test_calendar_configs_share_topic_parents_and_split_directions(self):
        calendar_root = ROOT / "decks/calendar"
        calendar_dirs = config_dirs(calendar_root)
        self.assertEqual(len(calendar_dirs), 3)
        self.assertFalse((calendar_root / "deck.toml").exists())
        expected = {
            "japanese-months": (2601010103, 2601010104, 2601010203, "和風月名", "月→和風月名", "和風月名→月"),
            "sekki": (2601010105, 2601010106, 2601010205, "二十四節気", "太陽黄経→節気", "節気→太陽黄経"),
            "eto": (2601010107, 2601010108, 2601010207, "干支", "読み・順番→干支", "干支→読み・順番"),
        }
        for deck_dir in calendar_dirs:
            config = read_config(deck_dir)
            deck = config["deck"]
            forward_id, model_id, reverse_id, topic, forward, reverse = expected[deck_dir.name]
            parent = f"暦::{topic}"
            self.assertEqual(deck["name"], f"{parent}::{forward}")
            self.assertEqual(deck["id"], forward_id)
            self.assertEqual(deck["model_id"], model_id)
            self.assertEqual(deck["reverse_deck"]["id"], reverse_id)
            self.assertEqual(deck["reverse_deck"]["name"], f"{parent}::{reverse}")
            self.assertTrue(deck["include_reverse"])
            self.assertEqual(len(deck["name"].split("::")), 3)

    def _assert_package_contains_configs(self, archive_path: Path, deck_dirs: list[Path], result: tuple[int, int]):
        notes, cards, decks = inspect_package(archive_path, self.temp_root)
        expected_notes: dict[str, tuple[str, dict]] = {}
        expected_decks: dict[str, str] = {}
        expected_cards: set[tuple[str, int, int]] = set()
        for deck_dir in deck_dirs:
            config, facts, _ = load_deck(deck_dir)
            deck = config["deck"]
            deck_id = int(deck["id"])
            expected_decks[str(deck_id)] = deck["name"]
            reverse = deck.get("reverse_deck")
            if reverse:
                expected_decks[str(int(reverse["id"]))] = reverse["name"]
            for fact in facts:
                guid = genanki.guid_for(fact["fact_id"])
                self.assertNotIn(guid, expected_notes)
                expected_notes[guid] = (fact["fact_id"], deck)
                expected_cards.add((guid, 0, deck_id))
                if reverse:
                    expected_cards.add((guid, 1, int(reverse["id"])))

        self.assertEqual(len(notes), result[0])
        self.assertEqual(len(cards), result[1])
        self.assertEqual(set(notes), set(expected_notes))
        self.assertEqual(set(cards), expected_cards)
        for guid, fact_id in notes.items():
            self.assertEqual(fact_id, expected_notes[guid][0])
        for deck_id, expected_name in expected_decks.items():
            self.assertEqual(decks[deck_id]["name"], expected_name)
        return notes, cards

    def test_country_bundle_builders_package_only_region_shards(self):
        outputs = self.temp_root / "country-builds"
        requested: list[tuple[list[Path], Path, tuple[int, int]]] = []

        def build_to_temp(deck_dirs: list[Path], output_path: Path) -> tuple[int, int]:
            temp_output = outputs / output_path.name
            result = build_package(deck_dirs, temp_output)
            requested.append((list(deck_dirs), temp_output, result))
            return result

        with patch.object(build_country_bundles, "build_package", side_effect=build_to_temp):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(build_country_bundles.main(), 0)

        self.assertEqual({path.name for _, path, _ in requested}, {"country-capital-pack.apkg", "country-flag-pack.apkg"})
        by_name = {path.name: (deck_dirs, path, result) for deck_dirs, path, result in requested}
        capital_dirs, capital_path, capital_result = by_name["country-capital-pack.apkg"]
        expected_capital_dirs = [
            path.parent
            for family in ("starter-capitals", "starter-names")
            for path in (ROOT / "decks/countries" / family).glob("*/deck.toml")
        ]
        self.assertEqual({path.resolve() for path in capital_dirs}, {path.resolve() for path in expected_capital_dirs})
        self.assertEqual(capital_result, (392, 392))
        self._assert_package_contains_configs(capital_path, capital_dirs, capital_result)

        flag_dirs, flag_path, flag_result = by_name["country-flag-pack.apkg"]
        expected_flag_dirs = [path.parent for path in (ROOT / "decks/countries/starter-flags").glob("*/deck.toml")]
        self.assertEqual({path.resolve() for path in flag_dirs}, {path.resolve() for path in expected_flag_dirs})
        self.assertEqual(flag_result, (196, 196))
        self._assert_package_contains_configs(flag_path, flag_dirs, flag_result)

    def test_constellation_bundle_builders_package_only_seasonal_shards(self):
        outputs = self.temp_root / "constellation-builds"
        requested: list[tuple[list[Path], Path, tuple[int, int]]] = []

        def build_to_temp(deck_dirs: list[Path], output_path: Path) -> tuple[int, int]:
            temp_output = outputs / output_path.name
            result = build_package(deck_dirs, temp_output)
            requested.append((list(deck_dirs), temp_output, result))
            return result

        with patch.object(build_constellation_bundles, "build_package", side_effect=build_to_temp):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(build_constellation_bundles.main(), 0)

        expected = {
            "constellation-name-pack.apkg": ("starter-name", (88, 176)),
            "main-stars-pack.apkg": ("starter-main-stars", (27, 54)),
            "constellation-visual-pack.apkg": ("starter-visual", (88, 88)),
        }
        self.assertEqual({path.name for _, path, _ in requested}, set(expected))
        for deck_dirs, output_path, result in requested:
            family, expected_result = expected[output_path.name]
            expected_dirs = [path.parent for path in (ROOT / "decks/constellations" / family).glob("*/deck.toml")]
            self.assertEqual({path.resolve() for path in deck_dirs}, {path.resolve() for path in expected_dirs})
            self.assertEqual(result, expected_result)
            self._assert_package_contains_configs(output_path, deck_dirs, result)


if __name__ == "__main__":
    unittest.main()
