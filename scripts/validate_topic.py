#!/usr/bin/env python3
"""Validate topic data and its generated Anki package."""

from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
import zipfile
from pathlib import Path

from lib.topic_deck import expected_card_count, load_deck, media_files_for


ROOT = Path(__file__).resolve().parents[1]


def validate_data(deck_dir: Path) -> tuple[dict, list[dict[str, str]], list[dict[str, str]]]:
    config, facts, sources = load_deck(deck_dir)
    deck_config = config["deck"]
    validation = config.get("validation", {})
    if len({row["fact_id"] for row in facts}) != len(facts):
        raise ValueError("Fact IDs must be unique")
    if any(not row["prompt"] or not row["answer"] for row in facts):
        raise ValueError("Facts must have both prompt and answer")
    if any(not row["url"].startswith("https://") for row in sources):
        raise ValueError("All source URLs must use HTTPS")
    source_ids = {row["source_id"] for row in sources}
    unknown_sources = {row["source_id"] for row in facts} - source_ids
    if unknown_sources:
        raise ValueError(f"Unknown source IDs: {sorted(unknown_sources)}")
    expected_rows = validation.get("expected_rows")
    if expected_rows is not None and len(facts) != expected_rows:
        raise ValueError(f"Expected {expected_rows} facts, found {len(facts)}")
    expected_categories = set(validation.get("required_categories", []))
    actual_categories = {row["category"] for row in facts}
    if not expected_categories <= actual_categories:
        raise ValueError(
            f"Missing categories: {sorted(expected_categories - actual_categories)}"
        )
    print(f"PASS data: {len(facts)} facts, {len(sources)} sources")
    return config, facts, sources


def validate_package(
    deck_dir: Path, config: dict, facts: list[dict[str, str]]
) -> None:
    package_path = deck_dir / "build" / f"{config['deck']['slug']}.apkg"
    if not package_path.is_file():
        raise ValueError(f"Missing package: {package_path}")
    with zipfile.ZipFile(package_path) as package:
        required = {"collection.anki2", "media"}
        missing = required - set(package.namelist())
        if missing:
            raise ValueError(f"Missing package files: {sorted(missing)}")
        media = json.loads(package.read("media"))
        expected_media = media_files_for(deck_dir, config["deck"], facts)
        expected_media_names = {path.name for path in expected_media}
        if set(media.values()) != expected_media_names:
            raise ValueError(
                f"Expected media files {sorted(expected_media_names)}, "
                f"found {sorted(media.values())}"
            )
        with tempfile.NamedTemporaryFile(suffix=".anki2") as database_file:
            database_file.write(package.read("collection.anki2"))
            database_file.flush()
            with sqlite3.connect(database_file.name) as connection:
                notes = connection.execute("select count(*) from notes").fetchone()[0]
                cards = connection.execute("select count(*) from cards").fetchone()[0]
                models_json = connection.execute("select models from col").fetchone()[0]
        models = json.loads(models_json)
        model = next(iter(models.values()))
        field_names = {field["name"] for field in model["flds"]}
        required_fields = {
            "Prompt",
            "Answer",
            "Reading",
            "Detail",
            "Source",
            "FactId",
            "PromptMedia",
            "AnswerMedia",
            "ReversePromptMedia",
            "ReverseAnswerMedia",
        }
        if not required_fields <= field_names:
            raise ValueError(f"Missing model fields: {sorted(required_fields - field_names)}")
        for template in model["tmpls"]:
            rendered = template["qfmt"] + template["afmt"]
            if "{{Source}}" in rendered:
                raise ValueError("The card template must not expose Source")
            if "{{Prompt}}" not in rendered and "{{ReversePrompt}}" not in rendered:
                raise ValueError("The card template is missing a prompt field")
            if "{{Answer}}" not in rendered and "{{ReverseAnswer}}" not in rendered:
                raise ValueError("The card template is missing an answer field")
        expected_cards = expected_card_count(config, facts)
        if notes != len(facts) or cards != expected_cards:
            raise ValueError(
                f"Expected {len(facts)} notes and {expected_cards} cards, "
                f"found {notes} and {cards}"
            )
    print(f"PASS package {package_path.name}: {notes} notes, {cards} cards")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deck", help="deck directory, e.g. decks/calendar")
    args = parser.parse_args()
    deck_dir = Path(args.deck)
    if not deck_dir.is_absolute():
        deck_dir = ROOT / deck_dir
    config, facts, _ = validate_data(deck_dir)
    validate_package(deck_dir, config, facts)
    print("PASS topic validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
