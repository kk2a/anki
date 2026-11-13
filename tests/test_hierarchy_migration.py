"""Protect user-created descendants and card identity during migration planning."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from migrate_deck_hierarchy import plan


class MigrationPlanTests(unittest.TestCase):
    def test_calendar_templates_split_without_recreating_cards(self):
        moves, obsolete = plan({
            'decks': {'和風月名': 100, '個人のデッキ': 101},
            'cards': [
                {'deckName': '和風月名', 'ord': 0, 'cardId': 1},
                {'deckName': '和風月名', 'ord': 1, 'cardId': 2},
                {'deckName': '個人のデッキ', 'ord': 0, 'cardId': 3},
            ],
        })
        self.assertEqual(moves, {
            '暦::和風月名::月→和風月名': [1],
            '暦::和風月名::和風月名→月': [2],
        })
        self.assertEqual(obsolete, ['和風月名'])

    def test_user_descendants_are_rejected_even_when_empty(self):
        for parent in ['首都（世界196か国）', '星座スターター', '和風月名']:
            with self.subTest(parent=parent), self.assertRaisesRegex(ValueError, 'Unexpected descendants'):
                plan({'decks': {parent: 1, parent + '::自作': 2}, 'cards': []})

    def test_unexpected_template_stops_before_mutations(self):
        with self.assertRaisesRegex(ValueError, 'Unexpected template ordinal'):
            plan({
                'decks': {'国名スターター::アジア': 100},
                'cards': [{'deckName': '国名スターター::アジア', 'ord': 1, 'cardId': 1}],
            })

    def test_full_set_requires_retained_counterparts_before_deletion(self):
        full = {'deckName': '首都（世界196か国）', 'ord': 0, 'cardId': 1,
                'fields': {'FactId': {'value': 'country-capital-jp'}}}
        regional = {'deckName': '首都スターター::アジア', 'ord': 0, 'cardId': 2,
                    'fields': {'FactId': {'value': 'starter-country-capital-jp'}}}
        state = {'decks': {'首都（世界196か国）': 1, '首都スターター::アジア': 2},
                 'cards': [full]}
        with self.assertRaisesRegex(ValueError, 'Missing regional/seasonal counterpart'):
            plan(state)
        state['cards'].append(regional)
        moves, _ = plan(state)
        self.assertEqual(moves, {'国・地域::首都::アジア::国名→首都': [2]})
        regional['deckName'] = '国・地域::首都::アジア::国名→首都'
        state['decks'] = {'首都（世界196か国）': 1, regional['deckName']: 2}
        moves, _ = plan(state)
        self.assertEqual(moves, {})


if __name__ == '__main__':
    unittest.main()
