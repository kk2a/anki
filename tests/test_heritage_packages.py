"""Both independently imported heritage directions must have distinct note IDs."""

import json
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from lib.topic_deck import build_package, load_deck


class HeritagePackageTests(unittest.TestCase):
    def test_directions_can_coexist_with_their_own_templates(self):
        base = ROOT / 'decks/world-heritage'
        identify = base / 'identify'
        attributes = base / 'attributes'
        _, names, _ = load_deck(identify)
        _, details, _ = load_deck(attributes)
        self.assertEqual({r['fact_id'] for r in details},
                         {'attributes-' + r['fact_id'] for r in names})
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'heritage.apkg'
            self.assertEqual(build_package([identify, attributes], output), (2546, 2546))
            with zipfile.ZipFile(output) as archive:
                database = Path(temp) / 'collection.anki2'
                database.write_bytes(archive.read('collection.anki2'))
            with sqlite3.connect(database) as connection:
                self.assertEqual(connection.execute('select count(distinct guid) from notes').fetchone()[0], 2546)
                counts = dict(connection.execute('select did,count(*) from cards group by did'))
                self.assertEqual(counts, {2601040101: 1273, 2601040103: 1273})
                models = json.loads(connection.execute('select models from col').fetchone()[0])
                self.assertNotEqual(models['2601040102']['name'], models['2601040104']['name'])
                self.assertIn('{{Prompt}}', models['2601040102']['tmpls'][0]['qfmt'])
                self.assertIn('{{ReversePrompt}}', models['2601040104']['tmpls'][0]['qfmt'])


if __name__ == '__main__':
    unittest.main()
