#!/usr/bin/env python3
"""Group constellation starters by NAOJ's 20:00 JST culmination months.

Source: https://www.nao.ac.jp/new-info/constellation.html
The existing detail field holds the source month. Month groups are a project
convention, not NAOJ's classification into spring/summer/autumn/winter.
Main stars inherit their constellation's month; chart questions remain one-way.
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path

from fetch_countries import write_tsv


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "decks/constellations"
SEASONS = (("spring", "春"), ("summer", "夏"), ("autumn", "秋"), ("winter", "冬"))
SOURCE_URL = "https://www.nao.ac.jp/new-info/constellation.html"


def read(name: str) -> list[dict[str, str]]:
    with (BASE / "data" / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def main() -> int:
    constellations = read("constellation-facts.tsv")
    if len(constellations) != 88:
        raise ValueError("Expected 88 constellations")
    mapping = []
    for fact in constellations:
        match = re.search(r"見頃：(\d+)月", fact["detail"])
        if not match:
            raise ValueError(f"Missing source month for {fact['fact_id']}")
        month = int(match[1])
        if not 1 <= month <= 12:
            raise ValueError(f"Invalid source month: {month}")
        # March-May, June-August, September-November, December-February.
        season = ("winter", "winter", "spring", "spring", "spring", "summer", "summer", "summer", "autumn", "autumn", "autumn", "winter")[month - 1]
        mapping.append({
            "abbreviation": fact["fact_id"].removeprefix("constellation-"),
            "name_ja": fact["reverse_answer"],
            "month": str(month),
            "season": season,
            "source_url": SOURCE_URL,
        })
    by_code = {row["abbreviation"]: row for row in mapping}
    by_name = {row["name_ja"]: row for row in mapping}
    if len(by_code) != 88 or len(by_name) != 88:
        raise ValueError("Constellation identities must be unique")
    write_tsv(BASE / "data/constellation-seasons.tsv", list(mapping[0]), mapping)

    kinds = (
        ("name", "constellation-facts.tsv", "constellation-name", "星座", 2601030102, "Constellation Fact", 2601031101, 88),
        ("visual", "constellation-visual-facts.tsv", "constellation-visual", "星座ビジュアル", 2601030202, "Constellation Visual Fact", 2601031201, 88),
        ("main-stars", "main-star-facts.tsv", "main-stars", "主要恒星", 2601030302, "Main Star Fact", 2601031301, 27),
    )
    for kind, filename, slug, category, model_id, model_name, base_id, expected in kinds:
        facts = read(filename)
        if len(facts) != expected:
            raise ValueError(f"Expected {expected} facts in {kind}")
        for fact in facts:
            if kind == "main-stars":
                name, marker, _ = fact["answer"].partition("座の")
                if not marker:
                    raise ValueError(f"Missing host constellation: {fact['fact_id']}")
                entry = by_name[name + "座"]
            else:
                entry = by_code[fact["fact_id"].rsplit("-", 1)[1]]
            fact["tags"] += f" constellation-starter season-{entry['season']}"
        fields = [field for field in facts[0] if not field.endswith("_media")]
        if kind == "visual":
            fields = list(facts[0])
        write_tsv(BASE / f"data/starter-{kind}-facts.tsv", fields, facts)
        counts = Counter(next(tag.removeprefix("season-") for tag in row["tags"].split() if tag.startswith("season-")) for row in facts)
        for index, (season, label) in enumerate(SEASONS):
            path = BASE / f"starter-{kind}" / season / "deck.toml"
            path.parent.mkdir(parents=True, exist_ok=True)
            title = {"name": "星座スターター", "visual": "星座（星図）スターター", "main-stars": "主要恒星スターター"}[kind]
            forward = f"{title}::{label}"
            if kind == "name":
                forward += "::日本語名→学名・略号"
            elif kind == "main-stars":
                forward += "::固有名→星座・符号"
            config = f'''[deck]
id = {base_id + 2 * index}
model_id = {model_id}
name = "{forward}"
slug = "{slug}-starter-{season}"
model_name = "{model_name}"
data_file = "../../data/starter-{kind}-facts.tsv"
sources_file = "../../data/sources.tsv"
include_reverse = {str(kind != 'visual').lower()}
fact_id_prefix = "starter-"
required_tags = ["season-{season}"]
'''
            if kind == "visual":
                config += 'media_dir = "../../assets/charts"\n'
            else:
                direction = "学名・略号→日本語名" if kind == "name" else "星座・符号→固有名"
                config += f'''\n[deck.reverse_deck]
id = {base_id + 2 * index + 1}
name = "{title}::{label}::{direction}"
'''
            config += f'''\n[validation]
expected_rows = {counts[season]}
required_categories = ["{category}"]
'''
            path.write_text(config, encoding="utf-8")
        print(f"Prepared {kind}: {dict(counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
