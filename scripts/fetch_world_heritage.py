#!/usr/bin/env python3
"""Fetch UNESCO's World Heritage dataset and generate topic TSV files."""

from __future__ import annotations

import argparse
import csv
import json
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_URL = "https://data.unesco.org/api/explore/v2.1/catalog/datasets/whc001/records"
DATA_DIR = ROOT / "decks/world-heritage/data"
SITES_PATH = DATA_DIR / "sites.tsv"
FACTS_PATH = DATA_DIR / "facts.tsv"
SOURCES_PATH = DATA_DIR / "sources.tsv"
JA_NAMES_PATH = DATA_DIR / "name_ja.tsv"
PAGE_SIZE = 100

CATEGORY_NAMES = {
    "Cultural": "文化遺産",
    "Natural": "自然遺産",
    "Mixed": "複合遺産",
}

SITE_FIELDS = [
    "id_no",
    "name_en",
    "name_ja",
    "reading",
    "short_description_en",
    "date_inscribed",
    "category",
    "criteria_txt",
    "states_names",
    "iso_codes",
    "region",
    "transboundary",
    "danger",
    "main_image_url",
    "main_image_author",
    "main_image_copyright",
    "site_url",
]

FACT_FIELDS = [
    "fact_id",
    "item_id",
    "question_type",
    "category",
    "prompt",
    "answer",
    "reading",
    "detail",
    "source_id",
    "tags",
    "reverse_prompt",
    "reverse_answer",
]


def clean(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ").split())


def compact_description(value: str, limit: int = 320) -> str:
    value = clean(value)
    if len(value) <= limit:
        return value
    boundary = value.rfind(". ", 0, limit)
    if boundary >= 120:
        return value[: boundary + 1]
    return value[:limit].rsplit(" ", 1)[0] + "…"


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def fetch_json(params: dict[str, int]) -> dict:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{API_URL}?{query}",
        headers={"User-Agent": "anki-decks-world-heritage/1.0"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def fetch_records() -> list[dict]:
    first_page = fetch_json({"limit": 1, "offset": 0})
    total_count = int(first_page["total_count"])
    records = []
    for offset in range(0, total_count, PAGE_SIZE):
        page = fetch_json({"limit": PAGE_SIZE, "offset": offset})
        records.extend(page["results"])
        print(f"fetched {len(records)}/{total_count}")
    if len(records) != total_count:
        raise ValueError(f"Expected {total_count} records, fetched {len(records)}")
    return records


def japanese_names() -> dict[str, tuple[str, str]]:
    return {
        row["id_no"]: (row["name_ja"], row.get("reading", ""))
        for row in read_tsv(JA_NAMES_PATH)
        if row.get("id_no") and row.get("name_ja")
    }


def normalise_site(record: dict, names: dict[str, tuple[str, str]]) -> dict[str, str]:
    id_no = clean(record.get("id_no"))
    name_en = clean(record.get("name_en"))
    name_ja, reading = names.get(id_no, ("", ""))
    return {
        "id_no": id_no,
        "name_en": name_en,
        "name_ja": name_ja,
        "reading": reading,
        "short_description_en": clean(record.get("short_description_en")),
        "date_inscribed": clean(record.get("date_inscribed")),
        "category": clean(record.get("category")),
        "criteria_txt": clean(record.get("criteria_txt")),
        "states_names": clean(", ".join(record.get("states_names") or [])),
        "iso_codes": clean(record.get("iso_codes")),
        "region": clean(record.get("region")),
        "transboundary": clean(record.get("transboundary")),
        "danger": clean(record.get("danger")),
        "main_image_url": clean(record.get("main_image_url")),
        "main_image_author": clean(record.get("main_image_author")),
        "main_image_copyright": clean(record.get("main_image_copyright")),
        "site_url": f"https://whc.unesco.org/en/list/{id_no}/",
    }


def write_tsv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def make_facts(sites: list[dict[str, str]]) -> list[dict[str, str]]:
    facts = []
    seen_ids = set()
    for site in sorted(sites, key=lambda row: int(row["id_no"])):
        id_no = site["id_no"]
        if id_no in seen_ids:
            raise ValueError(f"Duplicate UNESCO id_no: {id_no}")
        seen_ids.add(id_no)
        category = CATEGORY_NAMES.get(site["category"], site["category"])
        answer = site["name_ja"] or site["name_en"]
        summary = compact_description(site["short_description_en"])
        if not summary:
            summary = "登録情報を手がかりに答える。"
        clue = (
            f"{site['date_inscribed']}年登録。{site['states_names']}の{category}。"
            f"{summary} この世界遺産は？"
        )
        attributes = (
            f"登録年：{site['date_inscribed']}年／区分：{category}／"
            f"登録基準：{site['criteria_txt']}／所在国・地域：{site['states_names']}"
        )
        detail = (
            f"英語名：{site['name_en']}／国・地域：{site['states_names']}／"
            f"地域：{site['region']}／区分：{category}／登録年：{site['date_inscribed']}年／"
            f"登録基準：{site['criteria_txt']}／"
            f"{'危機遺産' if site['danger'] == 'True' else '危機遺産ではない'}／"
            f"公式ページ：{site['site_url']}"
        )
        facts.append(
            {
                "fact_id": f"world-heritage-{id_no}",
                "item_id": f"wh-{id_no}",
                "question_type": "clue-to-name",
                "category": "世界遺産",
                "prompt": clean(clue),
                "answer": answer,
                "reading": site["reading"],
                "detail": detail,
                "source_id": "unesco_datahub",
                "tags": f"world-heritage global {site['category'].lower()}",
                "reverse_prompt": f"「{answer}」の登録年・区分・登録基準・所在国は？",
                "reverse_answer": attributes,
            }
        )
    return facts


def write_sources() -> None:
    write_tsv(
        SOURCES_PATH,
        ["source_id", "title", "url", "accessed_at", "rights_note"],
        [
            {
                "source_id": "unesco_datahub",
                "title": "UNESCO DataHub: World Heritage List（whc001）",
                "url": "https://data.unesco.org/explore/dataset/whc001/",
                "accessed_at": "2026-10-20",
                "rights_note": "UNESCO DataHubの表示に従いCC BY-SA 4.0。再利用時はUNESCOの利用条件とデータセットのライセンスを確認する。",
            },
            {
                "source_id": "unesco_whc",
                "title": "UNESCO World Heritage Centre: World Heritage List",
                "url": "https://whc.unesco.org/en/list/",
                "accessed_at": "2026-10-20",
                "rights_note": "各物件の公式ページを確認するための参照先。物件ページに記載された情報と利用条件を優先する。",
            },
        ],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="use the existing sites.tsv without downloading")
    args = parser.parse_args()

    names = japanese_names()
    if args.offline:
        sites = read_tsv(SITES_PATH)
    else:
        sites = [normalise_site(record, names) for record in fetch_records()]
        write_tsv(SITES_PATH, SITE_FIELDS, sites)
    if not sites:
        raise ValueError("No UNESCO World Heritage records found")
    write_tsv(FACTS_PATH, FACT_FIELDS, make_facts(sites))
    write_sources()
    print(f"generated {len(sites)} World Heritage facts")
    print(f"Japanese names retained: {sum(bool(site.get('name_ja')) for site in sites)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
