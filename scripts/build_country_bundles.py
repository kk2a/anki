#!/usr/bin/env python3
"""Bundle country decks without changing their deck IDs or note GUIDs."""

from pathlib import Path

from lib.topic_deck import build_package


ROOT = Path(__file__).resolve().parents[1]
COUNTRIES = ROOT / "decks/countries"


def main() -> int:
    groups = {
        f"{slug}-starter": sorted(path.parent for path in (COUNTRIES / kind).glob("*/deck.toml"))
        for slug, kind in (
            ("country-name", "starter-names"),
            ("country-flag", "starter-flags"),
            ("country-capital", "starter-capitals"),
        )
    }
    for name, decks in groups.items():
        if len(decks) != 7:
            raise ValueError(f"Expected 7 regional deck configurations in {name}")
        output = COUNTRIES / "build" / f"{name}.apkg"
        notes, cards = build_package(decks, output)
        if notes != 196 or cards != 196:
            raise ValueError(f"Expected 196 notes/cards in {name}, found {notes}/{cards}")
        print(f"Wrote {len(decks)} decks, {notes} notes and {cards} cards to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
