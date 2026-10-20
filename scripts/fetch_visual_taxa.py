#!/usr/bin/env python3
"""Select Commons images and generate visual-deck TSV files from species lists."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
ALLOWED_LICENSE_MARKERS = ("public domain", "cc0", "cc by")
REJECTED_TITLE_MARKERS = (
    "diagram",
    "distribution",
    "map",
    "range",
    "skeleton",
    "anatomy",
    "illustration",
    "drawing",
    "logo",
    "flag",
    "cooked",
    "dried",
    "market",
    "slice",
    "bee",
    "butterfly",
    "insect",
    "moth",
    "wasp",
    "bird",
)

FACT_FIELDS = [
    "fact_id",
    "item_id",
    "category",
    "prompt",
    "answer",
    "reading",
    "detail",
    "source_id",
    "tags",
    "asset_id",
    "prompt_media",
]
ASSET_FIELDS = [
    "asset_id",
    "filename",
    "download_url",
    "source_url",
    "author",
    "license",
    "license_url",
    "attribution",
    "accessed_at",
]
SOURCE_FIELDS = ["source_id", "title", "url", "accessed_at", "rights_note"]

TAXONOMY_SOURCES = {
    "fish": [
        {
            "source_id": "fishbase",
            "title": "FishBase",
            "url": "https://fishbase.se/",
            "rights_note": "学名・分類の参照元。利用条件とCC BY-NC 4.0に従う。",
        }
    ],
    "plants": [
        {
            "source_id": "powo",
            "title": "Plants of the World Online",
            "url": "https://powo.science.kew.org/",
            "rights_note": "学名・分類の参照元。データベースの利用条件に従う。",
        }
    ],
    "flowers": [
        {
            "source_id": "powo",
            "title": "Plants of the World Online",
            "url": "https://powo.science.kew.org/",
            "rights_note": "学名・分類の参照元。データベースの利用条件に従う。",
        }
    ],
    "mushrooms": [
        {
            "source_id": "maff_mushrooms",
            "title": "農林水産省 きのこを知ろう",
            "url": "https://www.maff.go.jp/j/pr/aff/2110/spe1_02.html",
            "rights_note": "きのこの一般情報を確認する参照元。",
        },
        {
            "source_id": "jataff_kinoko",
            "title": "日本特用林産振興会 きのこ図鑑",
            "url": "https://www.jataff.or.jp/kinoko/",
            "rights_note": "きのこの分類・特徴を確認する参照元。",
        },
    ],
}


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def clean(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.replace("\t", " ").replace("\r", " ").replace("\n", " ").split())


def fetch_candidates(search_term: str) -> list[dict]:
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": search_term,
        "gsrnamespace": 6,
        "gsrlimit": 20,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|mime|size",
        "format": "json",
    }
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{COMMONS_API}?{query}",
        headers={"User-Agent": "anki-decks-visual-assets/1.0"},
    )
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = json.load(response)
            return [
                {"title": page.get("title", ""), **(page.get("imageinfo") or [{}])[0]}
                for page in payload.get("query", {}).get("pages", {}).values()
            ]
        except urllib.error.HTTPError as error:
            if error.code != 429 or attempt == 5:
                raise
            retry_after = error.headers.get("Retry-After")
            delay = int(retry_after) if retry_after and retry_after.isdigit() else 10 * (2**attempt)
            print(f"rate limited for {search_term}; retry in {delay}s", flush=True)
            time.sleep(delay)
    return []


def license_info(candidate: dict) -> tuple[str, str] | None:
    metadata = candidate.get("extmetadata") or {}
    license_name = clean((metadata.get("LicenseShortName") or {}).get("value"))
    license_url = clean((metadata.get("LicenseUrl") or {}).get("value"))
    lowered = license_name.lower()
    if "nc" in lowered or "nd" in lowered:
        return None
    if not any(marker in lowered for marker in ALLOWED_LICENSE_MARKERS):
        return None
    return license_name, license_url


def choose_candidate(search_term: str, candidates: list[dict]) -> tuple[dict, str, str]:
    terms = [term.lower() for term in re.findall(r"[a-z0-9]+", search_term)]
    scored = []
    for candidate in candidates:
        title = candidate.get("title", "")
        title_lower = title.lower()
        info = license_info(candidate)
        mime = candidate.get("mime", "")
        if not info or mime not in {"image/jpeg", "image/png", "image/webp"}:
            continue
        if any(marker in title_lower for marker in REJECTED_TITLE_MARKERS):
            continue
        width = int(candidate.get("width") or 0)
        height = int(candidate.get("height") or 0)
        score = sum(5 for term in terms if term in title_lower)
        score += 4 if mime == "image/jpeg" else 2
        score += min(width * height / 1_000_000, 5)
        if min(width, height) >= 600:
            score += 3
        scored.append((score, candidate, info))
    if not scored:
        raise ValueError(f"No suitable Commons image found for {search_term}")
    _, candidate, info = max(scored, key=lambda item: item[0])
    return candidate, info[0], info[1]


def file_urls(title: str) -> tuple[str, str, str]:
    file_name = title.removeprefix("File:").replace(" ", "_")
    quoted = urllib.parse.quote(file_name, safe="()'!,._-")
    suffix = Path(file_name).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".jpg"
    source_url = f"https://commons.wikimedia.org/wiki/File:{quoted}"
    download_url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{quoted}?width=1280"
    return source_url, download_url, suffix


def generate_deck(deck_dir: Path) -> None:
    config_path = deck_dir / "deck.toml"
    with config_path.open("rb") as handle:
        config = tomllib.load(handle)
    deck = config["deck"]
    category = config["validation"]["required_categories"][0]
    theme = deck_dir.parent.name
    species_path = deck_dir.parent / "data/species.tsv"
    data_dir = deck_dir.parent / "data"
    species = read_tsv(species_path)
    today = date.today().isoformat()
    facts = []
    assets = []
    sources = [
        {
            **source,
            "accessed_at": today,
        }
        for source in TAXONOMY_SOURCES[theme]
    ]
    for index, item in enumerate(species, start=1):
        candidate, license_name, license_url = choose_candidate(
            item["search_term"], fetch_candidates(item["search_term"])
        )
        source_url, download_url, suffix = file_urls(candidate["title"])
        asset_id = f"commons-{item['item_id']}"
        filename = f"{item['item_id']}{suffix}"
        metadata = candidate.get("extmetadata") or {}
        author = clean((metadata.get("Artist") or {}).get("value")) or "不明"
        attribution = f"Source: Wikimedia Commons; author: {author}"
        assets.append(
            {
                "asset_id": asset_id,
                "filename": filename,
                "download_url": download_url,
                "source_url": source_url,
                "author": author,
                "license": license_name,
                "license_url": license_url,
                "attribution": attribution,
                "accessed_at": today,
            }
        )
        sources.append(
            {
                "source_id": asset_id,
                "title": candidate["title"],
                "url": source_url,
                "accessed_at": today,
                "rights_note": f"画像は{license_name}。再利用時は作者表示とライセンスURLを保持する。",
            }
        )
        taxonomy_source = TAXONOMY_SOURCES[theme][0]["source_id"]
        facts.append(
            {
                "fact_id": item["item_id"],
                "item_id": item["item_id"],
                "category": category,
                "prompt": f"この画像の{category}は？",
                "answer": item["answer"],
                "reading": item["reading"],
                "detail": (
                    f"学名：{item['scientific_name']}／"
                    f"分類・基本情報の参照：{TAXONOMY_SOURCES[theme][0]['title']}／"
                    f"画像：{author}（{license_name}）"
                ),
                "source_id": taxonomy_source,
                "tags": f"{theme} visual commons",
                "asset_id": asset_id,
                "prompt_media": filename,
            }
        )
        print(f"selected {index}/{len(species)} {item['answer']}: {candidate['title']}")
        time.sleep(0.4)
    write_tsv(data_dir / "facts.tsv", FACT_FIELDS, facts)
    write_tsv(data_dir / "assets.tsv", ASSET_FIELDS, assets)
    write_tsv(data_dir / "sources.tsv", SOURCE_FIELDS, sources)
    print(f"generated {len(facts)} facts for {theme}")


def configured_decks() -> list[Path]:
    decks = []
    for config_path in sorted((ROOT / "decks").glob("**/deck.toml")):
        with config_path.open("rb") as handle:
            config = tomllib.load(handle)
        if config.get("deck", {}).get("assets_file") and (config_path.parent.parent / "data/species.tsv").is_file():
            decks.append(config_path.parent)
    return decks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deck", nargs="?", help="visual deck directory")
    parser.add_argument("--all", action="store_true", help="generate every taxonomy visual deck")
    args = parser.parse_args()
    if args.all == bool(args.deck):
        parser.error("specify exactly one of a deck path or --all")
    deck_dirs = configured_decks() if args.all else [ROOT / args.deck]
    for deck_dir in deck_dirs:
        generate_deck(deck_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
