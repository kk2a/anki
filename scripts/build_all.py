#!/usr/bin/env python3
"""Regenerate and validate every Anki package in this repository.

By default this uses the data and media already present in the workspace.
Pass a refresh option when source data or downloaded media should be refreshed
before building.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOPIC_BUILDER = ROOT / "scripts/build_topic_deck.py"
TOPIC_VALIDATOR = ROOT / "scripts/validate_topic.py"
COUNTRY_FETCHER = ROOT / "scripts/fetch_countries.py"
COUNTRY_STARTER_GENERATOR = ROOT / "scripts/generate_country_starters.py"
CONSTELLATION_FETCHER = ROOT / "scripts/fetch_constellations.py"
WORLD_HERITAGE_FETCHER = ROOT / "scripts/fetch_world_heritage.py"
VISUAL_TAXA_FETCHER = ROOT / "scripts/fetch_visual_taxa.py"
VISUAL_ASSET_FETCHER = ROOT / "scripts/fetch_visual_assets.py"
KITAUJI_BUILDER = ROOT / "decks/kitauji/scripts/build_deck.py"
KITAUJI_FETCHER = ROOT / "decks/kitauji/scripts/fetch_members.py"
KITAUJI_VALIDATOR = ROOT / "decks/kitauji/scripts/validate_project.py"


def run(command: list[str]) -> None:
    display = " ".join(shlex.quote(part) for part in command)
    print(f"$ {display}")
    subprocess.run(command, cwd=ROOT, check=True)


def topic_decks() -> list[Path]:
    return sorted(
        config_path.parent
        for config_path in (ROOT / "decks").glob("**/deck.toml")
    )


def build_topic_decks() -> int:
    decks = topic_decks()
    for deck_dir in decks:
        relative_deck = deck_dir.relative_to(ROOT)
        run([sys.executable, str(TOPIC_BUILDER), str(relative_deck)])
        run([sys.executable, str(TOPIC_VALIDATOR), str(relative_deck)])
    return len(decks)


def build_kitauji() -> None:
    run([sys.executable, str(KITAUJI_BUILDER)])
    run([sys.executable, str(KITAUJI_VALIDATOR)])
    run([sys.executable, str(KITAUJI_BUILDER), "--all"])
    run([sys.executable, str(KITAUJI_VALIDATOR), "--all"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh-countries",
        action="store_true",
        help="download the country data and flag SVGs before building",
    )
    parser.add_argument(
        "--refresh-kitauji",
        action="store_true",
        help="download Kitauji member data and images before building",
    )
    parser.add_argument(
        "--refresh-constellations",
        action="store_true",
        help="download the IAU OAE text-free constellation PNGs before building",
    )
    parser.add_argument(
        "--refresh-visual-assets",
        action="store_true",
        help="download visual-deck images listed in their asset manifests before building",
    )
    parser.add_argument(
        "--refresh-world-heritage",
        action="store_true",
        help="download UNESCO World Heritage records and regenerate World Heritage TSVs",
    )
    parser.add_argument(
        "--refresh-visual-taxa",
        action="store_true",
        help="select Commons images and regenerate fish, plant, flower, and mushroom TSVs",
    )
    args = parser.parse_args()

    if args.refresh_countries:
        run([sys.executable, str(COUNTRY_FETCHER)])
    if args.refresh_kitauji:
        run(
            [
                sys.executable,
                str(KITAUJI_FETCHER),
                "--download-images",
                "--all-images",
            ]
        )
    if args.refresh_constellations:
        run([sys.executable, str(CONSTELLATION_FETCHER)])
    if args.refresh_world_heritage:
        run([sys.executable, str(WORLD_HERITAGE_FETCHER)])
    if args.refresh_visual_taxa:
        run([sys.executable, str(VISUAL_TAXA_FETCHER), "--all"])
    if args.refresh_visual_assets:
        run([sys.executable, str(VISUAL_ASSET_FETCHER), "--all"])

    run([sys.executable, str(COUNTRY_STARTER_GENERATOR)])
    topic_count = build_topic_decks()
    build_kitauji()
    print(f"PASS all builds: {topic_count} topic configs and 2 Kitauji packages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
