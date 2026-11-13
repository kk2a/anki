#!/usr/bin/env python3
"""Bundle country decks without changing their deck IDs or note GUIDs."""

from pathlib import Path

from lib.topic_deck import build_package


ROOT = Path(__file__).resolve().parents[1]
COUNTRIES = ROOT / "decks/countries"


def main() -> int:
    groups = {
        "country-capital-pack": sorted(
            path.parent for kind in ("starter-capitals", "starter-names")
            for path in (COUNTRIES / kind).glob("*/deck.toml")
        ),
        "country-flag-pack": sorted(
            path.parent for path in (COUNTRIES / "starter-flags").glob("*/deck.toml")
        ),
    }
    for name, decks in groups.items():
        expected = 392 if name == "country-capital-pack" else 196
        if len(decks) != (14 if expected == 392 else 7):
            raise ValueError(f"Expected seven regions per direction in {name}")
        output = COUNTRIES / "build" / f"{name}.apkg"
        notes, cards = build_package(decks, output)
        if notes != expected or cards != expected:
            raise ValueError(f"Expected {expected} notes/cards in {name}, found {notes}/{cards}")
        print(f"Wrote {len(decks)} decks, {notes} notes and {cards} cards to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
