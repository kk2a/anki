#!/usr/bin/env python3
"""Bundle country decks without changing their deck IDs or note GUIDs."""

from pathlib import Path

from lib.topic_deck import build_package


ROOT = Path(__file__).resolve().parents[1]
COUNTRIES = ROOT / "decks/countries"


def main() -> int:
    groups = {
        f"{slug}-pack": [COUNTRIES / full] + sorted(path.parent for path in (COUNTRIES / kind).glob("*/deck.toml"))
        for slug, full, kind in (
            ("country-name", "country-name", "starter-names"),
            ("country-flag", "country-flag", "starter-flags"),
            ("country-capital", "capital", "starter-capitals"),
        )
    }
    for name, decks in groups.items():
        if len(decks) != 8:
            raise ValueError(f"Expected 1 full and 7 regional deck configurations in {name}")
        output = COUNTRIES / "build" / f"{name}.apkg"
        notes, cards = build_package(decks, output)
        if notes != 392 or cards != 392:
            raise ValueError(f"Expected 392 notes/cards in {name}, found {notes}/{cards}")
        print(f"Wrote {len(decks)} decks, {notes} notes and {cards} cards to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
