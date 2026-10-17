#!/usr/bin/env python3
"""Download the text-free IAU OAE constellation charts used by the visual deck."""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
FACTS = ROOT / "decks/constellations/data/constellation-visual-facts.tsv"
ASSET_DIR = ROOT / "decks/constellations/assets/charts"
CHART_BASE_URL = "https://astro4edu.org/media/diagrams/multimedia/blank"
CHART_BORDER = 12


def image_converter() -> str:
    converter = shutil.which("magick") or shutil.which("convert")
    if converter is None:
        raise RuntimeError(
            "ImageMagick is required to crop constellation charts "
            "(install either 'magick' or 'convert')"
        )
    return converter


def chart_content_geometry(source: Path) -> tuple[int, int, int, int]:
    """Return the non-white content box as width, height, x, y."""
    converter = image_converter()
    result = subprocess.run(
        [
            converter,
            str(source),
            "-alpha",
            "off",
            "-colorspace",
            "gray",
            "-threshold",
            "99%",
            "-negate",
            "-trim",
            "-format",
            "%wx%h%O",
            "info:",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    match = re.fullmatch(r"(\d+)x(\d+)([+-]\d+)([+-]\d+)", result.stdout.strip())
    if match is None:
        raise ValueError(f"Could not detect chart content in {source}: {result.stdout!r}")
    width, height, x, y = (int(value) for value in match.groups())
    if width <= 0 or height <= 0:
        raise ValueError(f"Detected empty chart content in {source}")
    return width, height, x, y


def crop_chart(source: Path, target: Path) -> None:
    """Crop whitespace while keeping the chart's legend and attribution."""
    converter = image_converter()
    width, height, x, y = chart_content_geometry(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=target.parent, prefix=f".{target.name}.", suffix=".png", delete=False
    ) as handle:
        temporary = Path(handle.name)
    try:
        subprocess.run(
            [
                converter,
                str(source),
                "-crop",
                f"{width}x{height}+{x}+{y}",
                "+repage",
                "-bordercolor",
                "white",
                "-border",
                str(CHART_BORDER),
                str(temporary),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def chart_names() -> list[str]:
    with FACTS.open(encoding="utf-8", newline="") as handle:
        rows = csv.DictReader(handle, delimiter="\t")
        names = sorted(
            {
                media_name.strip()
                for row in rows
                if row.get("category") == "星座ビジュアル" and row.get("prompt_media")
                for media_name in row["prompt_media"].split(";")
            }
        )
    if len(names) != 89:
        raise ValueError(f"Expected 89 chart filenames (Serpens has two charts), found {len(names)}")
    return names


def download_chart(filename: str, force: bool) -> str:
    target = ASSET_DIR / filename
    if target.is_file() and not force:
        crop_chart(target, target)
        return "cropped"

    stem = Path(filename).stem
    url = f"{CHART_BASE_URL}/{stem}-constellation-map_blank.png"
    request = Request(url, headers={"User-Agent": "anki-decks/0.1 constellation fetcher"})
    with urlopen(request, timeout=30) as response:
        content = response.read()
    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"Unexpected chart content for {url}")

    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=ASSET_DIR, prefix=f".{filename}.", suffix=".png", delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(content)
    try:
        crop_chart(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return "downloaded"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="download even when the chart exists")
    args = parser.parse_args()

    counts = {"cropped": 0, "downloaded": 0}
    for filename in chart_names():
        status = download_chart(filename, args.force)
        counts[status] += 1
        print(f"{status}: {filename}")
    print(
        f"PASS constellation charts: {counts['downloaded']} downloaded, "
        f"{counts['cropped']} cropped"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
