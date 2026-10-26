#!/usr/bin/env python3
"""Fetch the Japanese 196-country list and prepare country Anki source data."""

from __future__ import annotations

import argparse
import csv
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "decks/countries/data"
FLAGS_DIR = ROOT / "decks/countries/assets/flags"
LIST_URL = "https://tools.digrart.jp/world-flags/"
FLAG_BASE_URL = "https://flagcdn.com/"
FLAG_SOURCE_URL = "https://www.sekainokokki.jp/organization/un#toc-members"
EXPECTED_COUNTRIES = 196

ENTRY_RE = re.compile(
    r'{order:(?P<order>\d+),a2:"(?P<a2>[^"]+)",a3:"(?P<a3>[^"]+)",'
    r'flagFileName:"(?P<flag>[^"]+)",name:"(?P<name>[^"]*)",'
    r'formal:"(?P<formal>[^"]*)",region:"(?P<region>[^"]*)",'
    r'capital:"(?P<capital>[^"]*)",capitalQuiz:!(?P<quiz>[01]),'
    r'capitalNote:"(?P<note>[^"]*)",pop2025:'
)

FACT_FIELDS = [
    "fact_id",
    "category",
    "prompt",
    "answer",
    "reading",
    "detail",
    "source_id",
    "tags",
    "reverse_prompt",
    "reverse_answer",
    "prompt_media",
    "answer_media",
    "reverse_prompt_media",
    "reverse_answer_media",
]
COUNTRY_FIELDS = [
    "country_id",
    "country_name",
    "formal_name",
    "capital_name",
    "capital_note",
    "region",
    "flag_code",
    "source_id",
    "tags",
]
SOURCE_FIELDS = ["source_id", "title", "url", "accessed_at", "rights_note"]


def fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "anki-decks-country-fetch/1.0"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def fetch_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "anki-decks-country-fetch/1.0"})
    with urlopen(request, timeout=30) as response:
        return response.read()


def parse_countries(data_js: str) -> list[dict[str, str]]:
    matches = [match.groupdict() for match in ENTRY_RE.finditer(data_js)]
    if len(matches) != EXPECTED_COUNTRIES:
        raise ValueError(
            f"Expected {EXPECTED_COUNTRIES} countries in source, found {len(matches)}"
        )

    rows = []
    for row in matches:
        row["country_id"] = row.pop("a2")
        row["flag_code"] = row.pop("flag").removesuffix(".svg").lower()
        row["country_name"] = row.pop("name")
        row["formal_name"] = row.pop("formal")
        row["capital_name"] = row.pop("capital")
        row["capital_note"] = row.pop("note")
        row.pop("a3")
        row.pop("order")
        row.pop("quiz")
        row["source_id"] = "country_list"
        row["tags"] = f"country {row['region']}"
        rows.append(row)

    by_id = {row["country_id"]: row for row in rows}
    if len(by_id) != EXPECTED_COUNTRIES:
        raise ValueError("Country codes must be unique")

    # The source treats city-state capitals as implicit. Make the answer explicit
    # so every card in the capital deck has a non-empty answer.
    by_id["SG"]["capital_name"] = "シンガポール"
    by_id["SG"]["capital_note"] = "都市国家のため、国名と首都名が同じ。"
    by_id["VA"]["capital_name"] = "バチカン市国"
    by_id["VA"]["capital_note"] = "都市国家のため、国名に首都の名称が含まれる。"
    return rows


def detail_for(row: dict[str, str]) -> str:
    detail = f"正式名称：{row['formal_name']}"
    if row["capital_note"]:
        detail += f"\n注記：{row['capital_note']}"
    return detail


def fact_row(
    fact_id: str,
    category: str,
    prompt: str,
    answer: str,
    detail: str,
    tags: str,
    reverse_prompt: str,
    reverse_answer: str,
    **media: str,
) -> dict[str, str]:
    return {
        "fact_id": fact_id,
        "category": category,
        "prompt": prompt,
        "answer": answer,
        "reading": "",
        "detail": detail,
        "source_id": "country_list",
        "tags": tags,
        "reverse_prompt": reverse_prompt,
        "reverse_answer": reverse_answer,
        "prompt_media": media.get("prompt_media", ""),
        "answer_media": media.get("answer_media", ""),
        "reverse_prompt_media": media.get("reverse_prompt_media", ""),
        "reverse_answer_media": media.get("reverse_answer_media", ""),
    }


def make_facts(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    name_facts = []
    capital_facts = []
    flag_facts = []
    for row in rows:
        country_id = row["country_id"].lower()
        name = row["country_name"]
        capital = row["capital_name"]
        detail = detail_for(row)
        base_tags = row["tags"]
        name_facts.append(
            fact_row(
                f"country-name-{country_id}",
                "国名",
                f"首都が{capital}の国名は？",
                name,
                detail,
                f"{base_tags} country-name",
                "",
                "",
            )
        )
        capital_facts.append(
            fact_row(
                f"country-capital-{country_id}",
                "首都",
                f"{name}の首都は？",
                capital,
                detail,
                f"{base_tags} country-capital",
                "",
                "",
            )
        )
        flag_facts.append(
            fact_row(
                f"country-flag-{country_id}",
                "国旗",
                "この国旗の国名は？",
                name,
                f"首都：{capital}\n{detail}",
                f"{base_tags} country-flag",
                "",
                "",
                prompt_media=f"flagpedia-{row['flag_code']}.svg",
            )
        )
        flag_facts[-1]["source_id"] = "country_flags"
    return {"country-name": name_facts, "capital": capital_facts, "flag": flag_facts}


def write_tsv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def write_sources(accessed_at: str, *, cached_countries: bool = False) -> None:
    rows = [
        {
            "source_id": "country_list",
            "title": "digtools 世界の国旗一覧・首都一覧（外務省公表196か国基準）",
            "url": LIST_URL,
            "accessed_at": accessed_at,
            "rights_note": "日本語の国名・首都名を学習用に転記。最新情報は外務省の基礎データで再確認する。",
        },
        {
            "source_id": "mofa_basic",
            "title": "外務省 キッズ外務省「世界の国々 基本情報を調べてみよう！」",
            "url": "https://www.mofa.go.jp/mofaj/kids/ichiran/basic.html",
            "accessed_at": accessed_at,
            "rights_note": "国名・首都の照合用。外務省の注記を優先して個別カードの注記を更新する。",
        },
        {
            "source_id": "country_flags",
            "title": "Sekainokokki.jp 国旗画像（Flagpedia / flagcdn.com）",
            "url": FLAG_SOURCE_URL,
            "accessed_at": accessed_at,
            "rights_note": "国旗画像はパブリックドメイン（https://flagpedia.net/terms）。公式CDN（https://www.sekainokokki.jp/download/api）から元の縦横比のSVGを取得しAPKGに同梱。国名・首都はcountry_listを参照。対象196か国は既存の外務省基準を維持し、国連加盟193か国に限定しない。",
        },
    ]
    if cached_countries:
        with (DATA_DIR / "sources.tsv").open(encoding="utf-8", newline="") as handle:
            previous = {row["source_id"]: row for row in csv.DictReader(handle, delimiter="\t")}
        rows = [
            previous.get(row["source_id"], row)
            if row["source_id"] != "country_flags" else row
            for row in rows
        ]
    write_tsv(DATA_DIR / "sources.tsv", SOURCE_FIELDS, rows)


def download_flags(rows: list[dict[str, str]]) -> None:
    FLAGS_DIR.mkdir(parents=True, exist_ok=True)

    def download(row: dict[str, str]) -> str:
        filename = f"{row['flag_code']}.svg"
        target = FLAGS_DIR / f"flagpedia-{filename}"
        if not target.exists():
            content = fetch_bytes(urljoin(FLAG_BASE_URL, filename))
            if ET.fromstring(content).tag != "{http://www.w3.org/2000/svg}svg":
                raise ValueError(f"Invalid flag SVG: {filename}")
            temporary = target.with_suffix(".svg.tmp")
            temporary.write_bytes(content)
            temporary.replace(target)
        return target.name

    with ThreadPoolExecutor(max_workers=4) as executor:
        for index, filename in enumerate(executor.map(download, rows), start=1):
            print(f"flag {index}/{len(rows)} {filename}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-flags", action="store_true", help="do not download SVG flags")
    parser.add_argument(
        "--cached-countries", action="store_true",
        help="reuse countries.tsv without fetching country names or capitals",
    )
    parser.add_argument(
        "--accessed-at",
        default=date.today().isoformat(),
        help="date recorded in sources.tsv (YYYY-MM-DD)",
    )
    args = parser.parse_args()

    if args.cached_countries:
        with (DATA_DIR / "countries.tsv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        if (
            len(rows) != EXPECTED_COUNTRIES
            or len({row["country_id"] for row in rows}) != EXPECTED_COUNTRIES
        ):
            raise ValueError("Expected 196 unique countries in countries.tsv")
    else:
        page_html = fetch_text(LIST_URL)
        app_match = re.search(r'<script type="module" src="([^"]+world-flags[^"/]*\.js)"', page_html)
        if not app_match:
            raise ValueError("Could not find the world-flags data script in the source page")
        app_url = urljoin(LIST_URL, app_match.group(1))
        app_js = fetch_text(app_url)
        data_match = re.search(r'from"([^"]*countries\.[^"]+\.js)"', app_js)
        if not data_match:
            raise ValueError("Could not find the country data module in the app script")
        data_js = fetch_text(urljoin(app_url, data_match.group(1)))
        rows = parse_countries(data_js)
    facts = make_facts(rows)
    if not args.skip_flags:
        download_flags(rows)

    write_tsv(DATA_DIR / "countries.tsv", COUNTRY_FIELDS, rows)
    for slug, slug_facts in facts.items():
        fields = [
            field for field in FACT_FIELDS
            if not field.startswith("reverse_") and not field.endswith("_media")
        ]
        if slug == "flag":
            fields.append("prompt_media")
        write_tsv(DATA_DIR / f"{slug}-facts.tsv", fields, slug_facts)
    write_sources(args.accessed_at, cached_countries=args.cached_countries)
    print(f"Prepared {len(rows)} countries under {DATA_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
