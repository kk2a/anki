#!/usr/bin/env python3
"""Generate independent country starters from the reviewed MOFA region mapping.

Region source: https://www.mofa.go.jp/mofaj/area/index.html
Per-country sources and review notes: decks/countries/data/country-regions.tsv.
Source metadata stays in starter-sources.tsv; card details use the full deck text.
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from fetch_countries import SOURCE_FIELDS, write_tsv


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "decks/countries/data"
REGIONS = {
    "アジア": ("asia", 22),
    "中東": ("middleeast", 15),
    "欧州": ("europe", 54),
    "アフリカ": ("africa", 54),
    "北米": ("n_america", 2),
    "中南米": ("latinamerica", 33),
    "大洋州": ("pacific", 16),
}


def read_rows(name: str) -> list[dict[str, str]]:
    with (DATA_DIR / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def main() -> int:
    mapping = read_rows("country-regions.tsv")
    regions = {row["country_id"]: row for row in mapping}
    countries = read_rows("countries.tsv")
    if len(mapping) != len(regions) or set(regions) != {row["country_id"] for row in countries}:
        raise ValueError("MOFA mapping must cover every country exactly once")
    if Counter(row["region"] for row in mapping) != Counter({name: count for name, (_, count) in REGIONS.items()}):
        raise ValueError("MOFA region counts changed; review mapping and deck expectations")
    for row in mapping:
        slug = REGIONS[row["region"]][0]
        if row["source_url"] != f"https://www.mofa.go.jp/mofaj/area/{slug}.html":
            raise ValueError(f"Unexpected MOFA source for {row['country_id']}")
        if row["country_id"] == "JP" and not row["note"]:
            raise ValueError("Japan supplement must be documented")

    source_by_id = {row["source_id"]: row for row in read_rows("sources.tsv")}
    sources = list(source_by_id.values())
    for name, (slug, _) in REGIONS.items():
        entries = [row for row in mapping if row["region"] == name]
        sources.append({
            "source_id": f"mofa_region_{slug}",
            "title": f"外務省 地域別インデックス（{name}）",
            "url": entries[0]["source_url"],
            "accessed_at": min(row["checked_at"] for row in entries),
            "rights_note": "地域分類の出典。国旗画像はcountry_flags、国名・首都はcountry_listを参照。日本のみ外国一覧に掲載がないためアジアとして補完。",
        })
    for kind, prefix in (("flag", "country-flag"), ("country-name", "country-name"), ("capital", "country-capital")):
        facts = read_rows(f"{kind}-facts.tsv")
        if len(facts) != len(regions) or {row["fact_id"] for row in facts} != {f"{prefix}-{code.lower()}" for code in regions}:
            raise ValueError(f"{kind} facts and MOFA region mapping differ")
        for fact in facts:
            code = fact["fact_id"].removeprefix(f"{prefix}-").upper()
            row = regions[code]
            slug = REGIONS[row["region"]][0]
            tags = [tag for tag in fact["tags"].split() if tag not in REGIONS]
            fact["tags"] = " ".join(tags + [row["region"], f"{prefix}-starter"])
            fact["source_id"] = f"mofa_region_{slug}"
        write_tsv(DATA_DIR / f"starter-{kind}-facts.tsv", list(facts[0]), facts)
        print(f"Prepared {len(facts)} {kind} starter facts from the MOFA mapping")
    write_tsv(DATA_DIR / "starter-sources.tsv", SOURCE_FIELDS, sources)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
