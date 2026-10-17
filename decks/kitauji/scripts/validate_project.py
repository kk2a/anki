#!/usr/bin/env python3
"""Validate the fetched member data, MVP assets, and generated Anki package."""

from __future__ import annotations

import csv
import json
import sqlite3
import tempfile
import argparse
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_MEMBER_COUNT = 91
EXPECTED_MVP_COUNT = 8
MEMBER_FIELDS = {
    "member_id",
    "name",
    "furigana",
    "grade",
    "instrument",
    "part",
    "profile",
    "detail_url",
    "image_url",
    "image_path",
    "source_url",
}
COMPETITION_FIELDS = {
    "event_id",
    "member_id",
    "selected",
    "member_source_url",
    "notes",
}
EVENT_FIELDS = {
    "event_id",
    "period",
    "school_year",
    "competition_level",
    "school_result",
    "source_url",
    "source_note",
}


def read_tsv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return list(reader), reader.fieldnames or []


def validate_data() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    members, member_fields = read_tsv(ROOT / "data/members.tsv")
    if set(member_fields) != MEMBER_FIELDS:
        raise ValueError(f"Unexpected member fields: {member_fields}")
    if len(members) != EXPECTED_MEMBER_COUNT:
        raise ValueError(f"Expected {EXPECTED_MEMBER_COUNT} members, found {len(members)}")
    for row in members:
        for field in ("member_id", "name", "grade", "instrument", "source_url"):
            if not row[field]:
                raise ValueError(f"Blank {field} for {row['member_id']}")
        if row["grade"] not in {"1", "2", "3"}:
            raise ValueError(f"Invalid grade for {row['member_id']}: {row['grade']}")
        if not row["source_url"].startswith("https://anime-eupho.com/"):
            raise ValueError(f"Unexpected source URL for {row['member_id']}")

    mvp, mvp_fields = read_tsv(ROOT / "data/mvp.tsv")
    if set(mvp_fields) != MEMBER_FIELDS:
        raise ValueError(f"Unexpected MVP fields: {mvp_fields}")
    if len(mvp) != EXPECTED_MVP_COUNT:
        raise ValueError(f"Expected {EXPECTED_MVP_COUNT} MVP rows, found {len(mvp)}")
    member_ids = {row["member_id"] for row in members}
    mvp_ids = {row["member_id"] for row in mvp}
    if not mvp_ids <= member_ids:
        raise ValueError(f"MVP contains unknown members: {sorted(mvp_ids - member_ids)}")
    for row in mvp:
        image_path = ROOT / row["image_path"]
        if not image_path.is_file() or image_path.stat().st_size == 0:
            raise ValueError(f"Missing MVP image: {image_path}")

    records, competition_fields = read_tsv(ROOT / "data/competition_records.tsv")
    if set(competition_fields) != COMPETITION_FIELDS:
        raise ValueError(f"Unexpected competition fields: {competition_fields}")
    events, event_fields = read_tsv(ROOT / "data/competition_events.tsv")
    if set(event_fields) != EVENT_FIELDS:
        raise ValueError(f"Unexpected event fields: {event_fields}")
    event_ids = {row["event_id"] for row in events}
    if any(row["event_id"] not in event_ids for row in records):
        raise ValueError("Competition records contain an unknown event_id")
    if any(not row["source_url"].startswith("https://") for row in events):
        raise ValueError("Competition events must have HTTPS sources")
    print(f"PASS data: {len(members)} members, {len(mvp)} MVP members")
    print(f"PASS competitions: {len(events)} events, {len(records)} member records")
    return members, mvp


def validate_package(rows: list[dict[str, str]], package_path: Path) -> None:
    with zipfile.ZipFile(package_path) as package:
        required = {"collection.anki2", "media"}
        missing = required - set(package.namelist())
        if missing:
            raise ValueError(f"Missing package files: {sorted(missing)}")
        media = json.loads(package.read("media"))
        expected_media = {Path(row["image_path"]).name for row in rows}
        if set(media.values()) != expected_media:
            raise ValueError(
                f"Unexpected media: expected {sorted(expected_media)}, "
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
        for field_name in ("Profile", "Furigana", "Part"):
            if field_name not in field_names:
                raise ValueError(f"Anki model is missing the {field_name} field")
        for template in model["tmpls"]:
            rendered = template["qfmt"] + template["afmt"]
            if "{{Source}}" in rendered or "<a " in rendered:
                raise ValueError("Anki card template still exposes a source link")
            if "{{Profile}}" not in template["afmt"]:
                raise ValueError("Anki answer template is missing the Profile field")
            if "{{Furigana}}" not in template["afmt"] and "{{Furigana}}" not in template["qfmt"]:
                raise ValueError("Anki card template is missing the Furigana field")
            if "{{Part}}" not in template["afmt"] and "{{Part}}" not in template["qfmt"]:
                raise ValueError("Anki card template is missing the Part field")
        if notes != len(rows) or cards != len(rows):
            raise ValueError(f"Expected {len(rows)} notes and cards, found {notes} and {cards}")
    print(f"PASS package {package_path.name}: {notes} notes, {cards} cards, {len(media)} media files")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="validate the full 91-member package")
    args = parser.parse_args()
    members, mvp = validate_data()
    rows = members if args.all else mvp
    package_path = ROOT / ("build/kitauji_all.apkg" if args.all else "build/kitauji_mvp.apkg")
    for row in rows:
        image_path = ROOT / row["image_path"]
        if not image_path.is_file() or image_path.stat().st_size == 0:
            raise ValueError(f"Missing image for package: {image_path}")
    validate_package(rows, package_path)
    print("PASS project validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
