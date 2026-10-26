"""Shared loading and building helpers for topic-based Anki decks."""

from __future__ import annotations

import csv
import html
import tomllib
from pathlib import Path
from typing import Any

import genanki
from genanki.card import Card


class DeckAssignedCard(Card):
    """Write a card into another deck while retaining its template ordinal."""

    def __init__(self, card: Card, target_deck_id: int):
        super().__init__(card.ord, card.suspend)
        self.target_deck_id = target_deck_id

    def write_to_db(self, cursor, timestamp, deck_id, note_id, id_gen, due=0):
        super().write_to_db(cursor, timestamp, self.target_deck_id, note_id, id_gen, due)


REQUIRED_FACT_FIELDS = {
    "fact_id",
    "category",
    "prompt",
    "answer",
    "reading",
    "detail",
    "source_id",
    "tags",
}
REQUIRED_SOURCE_FIELDS = {
    "source_id",
    "title",
    "url",
    "accessed_at",
    "rights_note",
}
MEDIA_FIELDS = (
    "prompt_media",
    "answer_media",
    "reverse_prompt_media",
    "reverse_answer_media",
)


def read_tsv(path: Path) -> tuple[list[dict[str, str]], set[str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return list(reader), set(reader.fieldnames or [])


def load_deck(deck_dir: Path) -> tuple[dict[str, Any], list[dict[str, str]], list[dict[str, str]]]:
    with (deck_dir / "deck.toml").open("rb") as handle:
        config = tomllib.load(handle)
    deck_config = config["deck"]
    facts, fact_fields = read_tsv(deck_dir / deck_config["data_file"])
    sources, source_fields = read_tsv(deck_dir / deck_config["sources_file"])
    missing_fact_fields = REQUIRED_FACT_FIELDS - fact_fields
    missing_source_fields = REQUIRED_SOURCE_FIELDS - source_fields
    if missing_fact_fields:
        raise ValueError(f"Missing fact fields: {sorted(missing_fact_fields)}")
    if missing_source_fields:
        raise ValueError(f"Missing source fields: {sorted(missing_source_fields)}")
    categories = deck_config.get("categories")
    if categories is None and deck_config.get("category") is not None:
        categories = [deck_config["category"]]
    if categories is not None:
        allowed_categories = set(categories)
        facts = [row for row in facts if row["category"] in allowed_categories]
    required_tags = set(deck_config.get("required_tags", []))
    if required_tags:
        facts = [row for row in facts if required_tags <= set(row["tags"].split())]
    fact_id_prefix = deck_config.get("fact_id_prefix", "")
    if fact_id_prefix:
        facts = [dict(row, fact_id=fact_id_prefix + row["fact_id"]) for row in facts]
    return config, facts, sources


def safe(value: str) -> str:
    return html.escape(value or "", quote=True)


def media_files_for(
    deck_dir: Path,
    deck_config: dict[str, Any],
    facts: list[dict[str, str]],
) -> list[Path]:
    media_dir_value = deck_config.get("media_dir")
    media_values = [
        media_name.strip()
        for row in facts
        for field in MEDIA_FIELDS
        for media_name in row.get(field, "").split(";")
        if media_name.strip()
    ]
    if not media_values:
        return []
    if not media_dir_value:
        raise ValueError("Facts contain media fields but deck.media_dir is missing")

    media_dir = (deck_dir / media_dir_value).resolve()
    files: dict[str, Path] = {}
    for value in media_values:
        relative = Path(value)
        if relative.is_absolute() or relative.name != value:
            raise ValueError(f"Media values must be simple filenames: {value}")
        path = (media_dir / relative).resolve()
        if media_dir not in path.parents or not path.is_file():
            raise ValueError(f"Missing media file: {path}")
        files[path.name] = path
    return [files[name] for name in sorted(files)]


def media_tag(filename: str) -> str:
    if not filename:
        return ""
    return "".join(
        f'<img class="card-media" src="{safe(Path(media_name).name)}" alt="">'
        for media_name in filename.split(";")
        if media_name.strip()
    )


def make_model(
    model_id: int,
    model_name: str,
    include_reverse: bool,
    card_direction: str | None = None,
) -> genanki.Model:
    forward_template = {
        "name": "基本",
        "ord": 0,
        "qfmt": '<div class="media">{{PromptMedia}}</div><div class="prompt">{{Prompt}}</div>',
        "afmt": (
            '{{FrontSide}}<hr id="answer">'
            '<div class="answer">{{Answer}}</div>'
            '<div class="media">{{AnswerMedia}}</div>'
            '<div class="reading">{{Reading}}</div>'
            '<div class="detail">{{Detail}}</div>'
        ),
    }
    reverse_template = {
        "name": "逆向き",
        "ord": 0,
        "qfmt": '<div class="media">{{ReversePromptMedia}}</div><div class="prompt">{{ReversePrompt}}</div>',
        "afmt": (
            '{{FrontSide}}<hr id="answer">'
            '<div class="answer">{{ReverseAnswer}}</div>'
            '<div class="media">{{ReverseAnswerMedia}}</div>'
            '<div class="reading">{{Reading}}</div>'
            '<div class="detail">{{Detail}}</div>'
        ),
    }
    if card_direction not in {None, "forward", "reverse"}:
        raise ValueError(f"Unsupported card_direction: {card_direction}")
    if card_direction == "reverse":
        templates = [reverse_template]
    else:
        templates = [forward_template]
        if include_reverse:
            reverse_template["ord"] = 1
            templates.append(reverse_template)
    return genanki.Model(
        model_id,
        model_name,
        fields=[
            {"name": "Prompt"},
            {"name": "Answer"},
            {"name": "Reading"},
            {"name": "Detail"},
            {"name": "Source"},
            {"name": "FactId"},
            {"name": "Tags"},
            {"name": "ReversePrompt"},
            {"name": "ReverseAnswer"},
            {"name": "PromptMedia"},
            {"name": "AnswerMedia"},
            {"name": "ReversePromptMedia"},
            {"name": "ReverseAnswerMedia"},
        ],
        templates=templates,
        css="""
.card {
  font-family: -apple-system, BlinkMacSystemFont, "Hiragino Kaku Gothic ProN", sans-serif;
  font-size: 22px;
  line-height: 1.55;
  text-align: center;
  color: #f8fafc;
  background: #243447;
  padding: 1em;
}
.prompt { font-size: 1.15em; font-weight: 700; }
.answer { font-size: 1.35em; font-weight: 700; color: #fef08a; }
.reading { margin-top: .35em; color: #bae6fd; }
.detail { margin: 1em auto 0; max-width: 36em; font-size: .82em; color: #e2e8f0; }
.media { margin: .5em auto; }
.card-media { max-width: 75vw; max-height: 14em; }
""",
    )


def expected_card_count(config: dict[str, Any], facts: list[dict[str, str]]) -> int:
    card_direction = config["deck"].get("card_direction")
    if card_direction == "reverse":
        return sum(
            bool(
                row.get("reverse_prompt")
                and (
                    row.get("reverse_answer")
                    or row.get("reverse_prompt_media")
                    or row.get("reverse_answer_media")
                )
            )
            for row in facts
        )
    if card_direction not in {None, "forward"}:
        raise ValueError(f"Unsupported card_direction: {card_direction}")
    include_reverse = bool(config["deck"].get("include_reverse", False))
    reverse_count = sum(
        bool(
            row.get("reverse_prompt")
            and (
                row.get("reverse_answer")
                or row.get("reverse_prompt_media")
                or row.get("reverse_answer_media")
            )
        )
        for row in facts
    )
    return len(facts) + (reverse_count if include_reverse else 0)


def prepare_deck(deck_dir: Path) -> tuple[genanki.Deck, list[Path], int]:
    config, facts, sources = load_deck(deck_dir)
    deck_config = config["deck"]
    reverse_deck = deck_config.get("reverse_deck")
    if reverse_deck and (
        not deck_config.get("include_reverse")
        or deck_config.get("card_direction") == "reverse"
        or int(reverse_deck["id"]) == int(deck_config["id"])
    ):
        raise ValueError("A separate reverse deck requires two directions and a distinct deck ID")
    source_ids = {row["source_id"] for row in sources}
    unknown_sources = {row["source_id"] for row in facts} - source_ids
    if unknown_sources:
        raise ValueError(f"Facts contain unknown source_id values: {sorted(unknown_sources)}")

    model = make_model(
        int(deck_config["model_id"]),
        deck_config["model_name"],
        bool(deck_config.get("include_reverse", False)),
        deck_config.get("card_direction"),
    )
    media_files = media_files_for(deck_dir, deck_config, facts)
    deck = genanki.Deck(int(deck_config["id"]), deck_config["name"])
    for row in facts:
        note = genanki.Note(
            model=model,
            fields=[
                safe(row["prompt"]),
                safe(row["answer"]),
                safe(row["reading"]),
                safe(row["detail"]),
                safe(row["source_id"]),
                safe(row["fact_id"]),
                safe(row["tags"]),
                safe(row.get("reverse_prompt", "")),
                safe(row.get("reverse_answer", "")),
                media_tag(row.get("prompt_media", "")),
                media_tag(row.get("answer_media", "")),
                media_tag(row.get("reverse_prompt_media", "")),
                media_tag(row.get("reverse_answer_media", "")),
            ],
            tags=[tag for tag in row["tags"].split() if tag],
        )
        note.guid = genanki.guid_for(row["fact_id"])
        if reverse_deck:
            note.cards = [
                DeckAssignedCard(card, int(reverse_deck["id"])) if card.ord == 1 else card
                for card in note.cards
            ]
        deck.add_note(note)

    return deck, media_files, expected_card_count(config, facts)


def build_package(deck_dirs: list[Path], output_path: Path) -> tuple[int, int]:
    decks = []
    media = {}
    guids = set()
    deck_ids = set()
    cards = 0
    for deck_dir in deck_dirs:
        deck, files, count = prepare_deck(deck_dir)
        config, _, _ = load_deck(deck_dir)
        additional = config["deck"].get("reverse_deck")
        associated = [deck]
        if additional:
            associated.append(genanki.Deck(int(additional["id"]), additional["name"]))
        for associated_deck in associated:
            if associated_deck.deck_id in deck_ids:
                raise ValueError(f"Duplicate deck ID: {associated_deck.deck_id}")
            deck_ids.add(associated_deck.deck_id)
        for note in deck.notes:
            if note.guid in guids:
                raise ValueError(f"Duplicate note GUID: {note.guid}")
            guids.add(note.guid)
        for path in files:
            if path.name in media and media[path.name] != path:
                raise ValueError(f"Conflicting media filename: {path.name}")
            media[path.name] = path
        decks.extend(associated)
        cards += count
    output_path.parent.mkdir(parents=True, exist_ok=True)
    genanki.Package(decks, media_files=[str(media[name]) for name in sorted(media)]).write_to_file(str(output_path))
    return len(guids), cards


def build_deck(deck_dir: Path, output_path: Path) -> tuple[int, int]:
    return build_package([deck_dir], output_path)
