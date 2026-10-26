#!/usr/bin/env python3
"""Bundle complete and seasonal constellation decks, retaining all identities."""

from pathlib import Path

from lib.topic_deck import build_package


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "decks/constellations"


def main() -> int:
    for kind, slug, notes, cards in (
        ("name", "constellation-name", 176, 352),
        ("main-stars", "main-stars", 54, 108),
        ("visual", "constellation-visual", 176, 176),
    ):
        seasonal = sorted(path.parent for path in (BASE / f"starter-{kind}").glob("*/deck.toml"))
        if len(seasonal) != 4:
            raise ValueError(f"Expected four seasonal configurations for {kind}")
        output = BASE / "build" / f"{slug}-pack.apkg"
        result = build_package([BASE / kind] + seasonal, output)
        if result != (notes, cards):
            raise ValueError(f"Unexpected {kind} note/card counts: {result}")
        print(f"Wrote {notes} notes and {cards} cards to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
