#!/usr/bin/env python3
"""Build an Anki package from the Kitauji member TSV files."""

from __future__ import annotations

import argparse
import csv
import html
import sys
from pathlib import Path

try:
    import genanki
except ImportError:
    print("genanki is required. Run: uv sync", file=sys.stderr)
    raise SystemExit(2)


ROOT = Path(__file__).resolve().parents[1]
DECK_ID = 1749215420
MODEL_ID = 1749215421


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def read_competitions(records_path: Path, events_path: Path) -> dict[str, str]:
    if not records_path.exists() or not events_path.exists():
        return {}
    events = {}
    with events_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            events[row["event_id"]] = row
    grouped: dict[str, list[str]] = {}
    with records_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if not row.get("member_id"):
                continue
            event = events.get(row.get("event_id", ""), {})
            period = event.get("period", "")
            level = event.get("competition_level", "")
            school_result = event.get("school_result", "")
            selected = row.get("selected", "")
            detail = " / ".join(value for value in (selected, school_result) if value)
            label = " ".join(value for value in (period, level, detail) if value)
            if label:
                grouped.setdefault(row["member_id"], []).append(label)
    return {member_id: "<br>".join(values) for member_id, values in grouped.items()}


def safe(value: str) -> str:
    return html.escape(value or "", quote=True)


def make_model(include_reverse: bool) -> genanki.Model:
    cards = [
        {
            "name": "顔から名前・属性",
            "ord": 0,
            "qfmt": '<div class="face">{{Face}}</div>',
            "afmt": (
                '{{FrontSide}}<hr id="answer">'
                '<div class="answer-name">{{Name}}</div>'
                '<div class="answer-furigana">{{Furigana}}</div>'
                '<div class="answer-meta">{{Instrument}} ／ {{Grade}}年生</div>'
                '<div class="answer-part">{{Part}}</div>'
                '<div class="profile">{{Profile}}</div>'
            ),
        }
    ]
    if include_reverse:
        cards.append(
            {
                "name": "名前から顔・属性",
                "ord": 1,
                "qfmt": (
                    '<div class="name-prompt">{{Name}}</div>'
                    '<div class="prompt-furigana">{{Furigana}}</div>'
                    '<div class="prompt-meta">{{Instrument}} ／ {{Grade}}年生</div>'
                    '<div class="prompt-part">{{Part}}</div>'
                ),
                "afmt": '{{FrontSide}}<hr id="answer"><div class="face">{{Face}}</div><div class="profile">{{Profile}}</div>',
            }
        )
    return genanki.Model(
        MODEL_ID,
        "Kitauji Member",
        fields=[
            {"name": "Name"},
            {"name": "Furigana"},
            {"name": "Grade"},
            {"name": "Instrument"},
            {"name": "Part"},
            {"name": "Profile"},
            {"name": "Face"},
            {"name": "Competition"},
            {"name": "Source"},
        ],
        templates=cards,
        css="""
.card { font-family: sans-serif; font-size: 20px; text-align: center; color: #fff; background: #243447; }
.face img { max-width: 80vw; max-height: 58vh; object-fit: contain; border-radius: 8px; }
.answer-name, .name-prompt { font-size: 1.5em; font-weight: 700; margin: 0.45em; }
.answer-furigana, .prompt-furigana { font-size: 0.9em; color: #fff; margin-top: -0.25em; }
.answer-meta, .prompt-meta { font-size: 1.05em; margin: 0.35em; }
.answer-part, .prompt-part {
  display: block;
  margin-top: 0.8em;
  color: #fff;
  font-size: 0.8em;
  font-weight: 700;
  letter-spacing: 0.04em;
}
.profile { margin: 1em auto 0; max-width: 38em; font-size: 0.85em; line-height: 1.55; text-align: left; }
""",
    )


def build(
    input_path: Path,
    output_path: Path,
    include_reverse: bool,
    competition_path: Path,
    deck_tag: str,
) -> None:
    rows = read_tsv(input_path)
    if not rows:
        raise ValueError(f"No members found in {input_path}")
    model = make_model(include_reverse)
    competitions = read_competitions(competition_path, ROOT / "data/competition_events.tsv")
    deck = genanki.Deck(DECK_ID, "北宇治高校吹奏楽部・顔と部員情報")
    media_files: list[str] = []
    for row in rows:
        image_path = ROOT / row["image_path"]
        if not image_path.is_file():
            raise FileNotFoundError(
                f"Missing image for {row['name']}: {image_path}. "
                "Run scripts/fetch_members.py --download-images first."
            )
        image_name = image_path.name
        media_files.append(str(image_path))
        note = genanki.Note(
            model=model,
            fields=[
                safe(row["name"]),
                safe(row["furigana"]),
                safe(row["grade"]),
                safe(row["instrument"]),
                safe(row["part"]),
                safe(row["profile"]),
                f'<img src="{image_name}">',
                competitions.get(row["member_id"], ""),
                safe(row["source_url"]),
            ],
            tags=["kitauji", deck_tag, f"grade{row['grade']}", row["member_id"]],
        )
        deck.add_note(note)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    genanki.Package(deck, media_files=media_files).write_to_file(str(output_path))
    print(f"Wrote {len(rows)} notes to {output_path}")
    print(f"Cards per note: {2 if include_reverse else 1}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="build cards for all 91 members")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--include-reverse", action="store_true")
    parser.add_argument("--tag", default=None, help="additional tag for generated notes")
    parser.add_argument(
        "--competition",
        type=Path,
        default=ROOT / "data/competition_records.tsv",
        help="TSV containing optional competition records",
    )
    args = parser.parse_args()
    input_path = args.input or (ROOT / "data/members.tsv" if args.all else ROOT / "data/mvp.tsv")
    output_path = args.output or (ROOT / "build/kitauji_all.apkg" if args.all else ROOT / "build/kitauji_mvp.apkg")
    deck_tag = args.tag or ("all-members" if args.all else "mvp")
    build(input_path, output_path, args.include_reverse, args.competition, deck_tag)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
