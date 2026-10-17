#!/usr/bin/env python3
"""Build a topic-based Anki package from a deck directory."""

from __future__ import annotations

import argparse
from pathlib import Path

from lib.topic_deck import build_deck


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deck", help="deck directory, e.g. decks/calendar")
    parser.add_argument("--output", type=Path, help="override the generated .apkg path")
    args = parser.parse_args()

    deck_dir = Path(args.deck)
    if not deck_dir.is_absolute():
        deck_dir = ROOT / deck_dir
    with (deck_dir / "deck.toml").open("rb") as handle:
        import tomllib

        config = tomllib.load(handle)
    default_output = deck_dir / "build" / f"{config['deck']['slug']}.apkg"
    output_path = args.output or default_output
    notes, cards = build_deck(deck_dir, output_path)
    print(f"Wrote {notes} notes and {cards} cards to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
