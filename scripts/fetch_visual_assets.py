#!/usr/bin/env python3
"""Download visual-deck assets listed in data/assets.tsv manifests."""

from __future__ import annotations

import argparse
import csv
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def configured_visual_decks() -> list[Path]:
    decks: list[Path] = []
    for config_path in sorted((ROOT / "decks").glob("**/deck.toml")):
        with config_path.open("rb") as handle:
            config = tomllib.load(handle)
        if config.get("deck", {}).get("assets_file"):
            decks.append(config_path.parent)
    return decks


def fetch_deck(deck_dir: Path, force: bool) -> None:
    with (deck_dir / "deck.toml").open("rb") as handle:
        config = tomllib.load(handle)["deck"]
    manifest_path = (deck_dir / config["assets_file"]).resolve()
    media_dir = (deck_dir / config["media_dir"]).resolve()
    media_dir.mkdir(parents=True, exist_ok=True)
    rows = read_tsv(manifest_path)
    for index, row in enumerate(rows):
        filename = Path(row["filename"])
        if filename.is_absolute() or filename.name != row["filename"]:
            raise ValueError(f"Asset filenames must be simple filenames: {row['filename']}")
        output_path = media_dir / filename
        if output_path.exists() and not force:
            print(f"skip {output_path}")
            continue
        request = urllib.request.Request(
            row["download_url"],
            headers={"User-Agent": "anki-decks-visual-assets/1.0"},
        )
        print(f"download {row['download_url']} -> {output_path}")
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    output_path.write_bytes(response.read())
                break
            except urllib.error.HTTPError as error:
                if error.code != 429 or attempt == 3:
                    raise
                delay = 5 * (2**attempt)
                print(f"rate limited; retry in {delay}s")
                time.sleep(delay)
        if index + 1 < len(rows):
            time.sleep(1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deck", nargs="?", help="visual deck directory")
    parser.add_argument("--all", action="store_true", help="fetch every configured visual deck")
    parser.add_argument("--force", action="store_true", help="overwrite existing assets")
    args = parser.parse_args()
    if args.all == bool(args.deck):
        parser.error("specify exactly one of a deck path or --all")
    deck_dirs = configured_visual_decks() if args.all else [ROOT / args.deck]
    for deck_dir in deck_dirs:
        print(f"$ fetch assets for {deck_dir.relative_to(ROOT)}")
        fetch_deck(deck_dir, args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
