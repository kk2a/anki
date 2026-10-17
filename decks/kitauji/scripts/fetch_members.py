#!/usr/bin/env python3
"""Fetch the official Kitauji member list and the selected MVP images."""

from __future__ import annotations

import argparse
import csv
import html
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIST_URL = "https://anime-eupho.com/special/member/"
BASE_URL = "https://anime-eupho.com"
IMAGE_ROOT = "/img/mv4r/special/member/"

# The first trial intentionally mixes grades and parts that are easy to confuse.
MVP_IDS = (
    "kumiko.oumae",
    "reina.kousaka",
    "mayu.kuroe",
    "kanade.hisaishi",
    "ririka.kenzaki",
    "satsuki.suzuki",
    "sari.yoshii",
    "suzume.kamaya",
)


def fetch(url: str, attempts: int = 4) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "kitauji-anki-personal-study/1.0"},
    )
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            if exc.code < 500 or attempt == attempts - 1:
                raise
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == attempts - 1:
                raise
            print(f"Temporary fetch error for {url}: {exc}; retrying", file=sys.stderr)
        time.sleep(2**attempt)
    raise RuntimeError(f"Unable to fetch {url}")


def clean(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    return " ".join(value.split())


def clean_lines(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    return "\n".join(" ".join(line.split()) for line in value.splitlines() if line.strip())


def parse_listing(source: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    part_pattern = re.compile(
        r'<div class="part">\s*<p class="part-name">(.*?)</p>.*?'
        r'<div class="member-list">(.*?)</div>\s*</div>',
        re.S,
    )
    member_pattern = re.compile(
        r'<a class="(grade[123])" href="([^"]+)">\s*'
        r'<img[^>]+src="([^"]+)"[^>]*>\s*<p>(.*?)</p>\s*</a>',
        re.S,
    )
    for part_match in part_pattern.finditer(source):
        part = clean(part_match.group(1))
        for member_match in member_pattern.finditer(part_match.group(2)):
            grade_class, detail_path, image_path, name = member_match.groups()
            member_id = Path(detail_path).stem
            rows.append(
                {
                    "member_id": member_id,
                    "name": clean(name),
                    "grade": grade_class[-1],
                    "part": part,
                    "detail_url": BASE_URL + detail_path,
                    "image_url": BASE_URL + image_path,
                }
            )
    return rows


def enrich_member(row: dict[str, str]) -> dict[str, str]:
    source = fetch(row["detail_url"])
    name_match = re.search(r'<p class="name">(.*?)</p>', source, re.S)
    furigana_match = re.search(r'<p class="furigana">(.*?)</p>', source, re.S)
    profile_match = re.search(r'<p class="txt">(.*?)</p>', source, re.S)
    profile_lines = clean_lines(profile_match.group(1)) if profile_match else ""
    profile = " ".join(profile_lines.splitlines())
    first_line = profile_lines.splitlines()[0] if profile_lines else ""
    grade_in_profile, instrument = ("", "")
    profile_parts = re.split(r"[／/]", first_line, maxsplit=1)
    if len(profile_parts) == 2:
        grade_in_profile = profile_parts[0].replace("年生", "").strip()
        instrument = profile_parts[1].strip()
    row["name"] = clean(name_match.group(1)) if name_match else row["name"]
    row["furigana"] = clean(furigana_match.group(1)) if furigana_match else ""
    row["grade"] = grade_in_profile or row["grade"]
    row["instrument"] = instrument
    row["profile"] = profile
    row["source_url"] = row["detail_url"]
    row["image_path"] = f"assets/member/{row['member_id']}.webp"
    return row


FIELDNAMES = (
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
)


def write_tsv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in FIELDNAMES} for row in rows)


def download(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "kitauji-anki-personal-study/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        path.write_bytes(response.read())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--download-images",
        action="store_true",
        help="download the official images for the MVP rows",
    )
    parser.add_argument(
        "--all-images",
        action="store_true",
        help="download images for all listed members instead of only the MVP",
    )
    args = parser.parse_args()

    print(f"Fetching {LIST_URL}")
    rows = [enrich_member(row) for row in parse_listing(fetch(LIST_URL))]
    if len(rows) != 91:
        raise RuntimeError(f"Expected 91 members, found {len(rows)}")
    write_tsv(ROOT / "data/members.tsv", rows)

    mvp_rows = [row for row in rows if row["member_id"] in MVP_IDS]
    if len(mvp_rows) != len(MVP_IDS):
        found = {row["member_id"] for row in mvp_rows}
        missing = sorted(set(MVP_IDS) - found)
        raise RuntimeError(f"MVP members were not found: {', '.join(missing)}")
    mvp_rows.sort(key=lambda row: MVP_IDS.index(row["member_id"]))
    write_tsv(ROOT / "data/mvp.tsv", mvp_rows)

    if args.download_images:
        target_rows = rows if args.all_images else mvp_rows
        for index, row in enumerate(target_rows, start=1):
            path = ROOT / row["image_path"]
            if not path.exists():
                print(f"Downloading image {index}/{len(target_rows)}: {row['name']}")
                download(row["image_url"], path)

    print(f"Wrote {len(rows)} members to data/members.tsv")
    print(f"Wrote {len(mvp_rows)} MVP members to data/mvp.tsv")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as exc:
        print(f"HTTP error while fetching official data: {exc}", file=sys.stderr)
        raise SystemExit(1)
