"""Check card placement and stable identities in packages with split directions."""

import csv
import json
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from lib.topic_deck import build_deck, build_package


class TopicPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "point.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
        self.write_tsv("facts.tsv", [{
            "fact_id": "sample-star", "category": "sample", "prompt": "Name?",
            "answer": "Alpha", "reading": "", "detail": "Shared explanation",
            "source_id": "sample", "tags": "sample", "reverse_prompt": "Alpha?",
            "reverse_answer": "Name", "prompt_media": "point.svg",
        }])
        self.write_tsv("sources.tsv", [{
            "source_id": "sample", "title": "Test fixture", "url": "https://example.com/",
            "accessed_at": "2026-10-26", "rights_note": "Generated test fixture",
        }])
        self.full = self.config("full", 901, 902, "")
        self.starter = self.config("starter", 903, 904, "starter-")

    def write_tsv(self, name, rows):
        with (self.root / name).open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)

    def config(self, name, forward_id, reverse_id, prefix):
        path = self.root / name
        path.mkdir()
        (path / "deck.toml").write_text(f'''[deck]
id = {forward_id}
model_id = 900
name = "{name} forward"
model_name = "Test model"
data_file = "../facts.tsv"
sources_file = "../sources.tsv"
media_dir = ".."
include_reverse = true
fact_id_prefix = "{prefix}"
[deck.reverse_deck]
id = {reverse_id}
name = "{name} reverse"
''')
        return path

    def inspect(self, path):
        with zipfile.ZipFile(path) as archive:
            database = self.root / "inspect.sqlite"
            database.write_bytes(archive.read("collection.anki2"))
            with sqlite3.connect(database) as connection:
                notes = dict(connection.execute("select guid, flds from notes"))
                cards = connection.execute(
                    "select n.guid, c.ord, c.did from notes n join cards c on c.nid=n.id"
                ).fetchall()
                decks = json.loads(connection.execute("select decks from col").fetchone()[0])
            media = json.loads(archive.read("media"))
        return notes, cards, decks, media

    def test_split_directions_and_independent_starter_share_media(self):
        single = self.root / "single.apkg"
        bundle = self.root / "bundle.apkg"
        self.assertEqual(build_deck(self.full, single), (1, 2))
        self.assertEqual(build_package([self.full, self.starter], bundle), (2, 4))
        original, _, _, _ = self.inspect(single)
        notes, cards, decks, media = self.inspect(bundle)
        full_guid = next(iter(original))
        self.assertEqual(notes[full_guid], original[full_guid])
        starter_guid = next(guid for guid in notes if guid != full_guid)
        self.assertEqual(set(cards), {
            (full_guid, 0, 901), (full_guid, 1, 902),
            (starter_guid, 0, 903), (starter_guid, 1, 904),
        })
        self.assertEqual(decks["902"]["name"], "full reverse")
        self.assertEqual(decks["904"]["name"], "starter reverse")
        self.assertEqual(list(media.values()), ["point.svg"])

    def test_duplicate_decks_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate deck ID"):
            build_package([self.full, self.full], self.root / "duplicate.apkg")

    def test_reverse_direction_needs_a_distinct_deck(self):
        invalid = self.config("invalid", 905, 905, "")
        with self.assertRaisesRegex(ValueError, "distinct deck ID"):
            build_deck(invalid, self.root / "invalid.apkg")


if __name__ == "__main__":
    unittest.main()
