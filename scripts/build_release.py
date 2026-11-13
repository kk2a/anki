#!/usr/bin/env python3
"""Stage the public v0.6.0 release from already-built topic APKGs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
RELEASE_FILES = (
    "japanese-months.apkg",
    "sekki.apkg",
    "eto.apkg",
    "country-capital-pack.apkg",
    "country-flag-pack.apkg",
    "constellation-name-pack.apkg",
    "main-stars-pack.apkg",
    "constellation-visual-pack.apkg",
    "world-heritage-identify.apkg",
    "world-heritage-attributes.apkg",
    "fish-visual.apkg",
    "plants-visual.apkg",
    "flowers-visual.apkg",
    "mushrooms-visual.apkg",
    "deck-sources.zip",
    "SHA256SUMS",
)
SOURCE_ZIP_NAME = "deck-sources.zip"
CHECKSUM_NAME = "SHA256SUMS"


class ReleaseError(Exception):
    """Raised when a release input or output fails its safety checks."""


@dataclass(frozen=True)
class PackageSpec:
    filename: str
    source: str
    theme: str
    notes: int
    cards: int


PACKAGE_SPECS = (
    PackageSpec("japanese-months.apkg", "decks/calendar/japanese-months/build/japanese-months.apkg", "calendar", 12, 24),
    PackageSpec("sekki.apkg", "decks/calendar/sekki/build/sekki.apkg", "calendar", 24, 48),
    PackageSpec("eto.apkg", "decks/calendar/eto/build/eto.apkg", "calendar", 72, 144),
    PackageSpec("country-capital-pack.apkg", "decks/countries/build/country-capital-pack.apkg", "countries", 392, 392),
    PackageSpec("country-flag-pack.apkg", "decks/countries/build/country-flag-pack.apkg", "countries", 196, 196),
    PackageSpec("constellation-name-pack.apkg", "decks/constellations/build/constellation-name-pack.apkg", "constellations", 88, 176),
    PackageSpec("main-stars-pack.apkg", "decks/constellations/build/main-stars-pack.apkg", "constellations", 27, 54),
    PackageSpec("constellation-visual-pack.apkg", "decks/constellations/build/constellation-visual-pack.apkg", "constellations", 88, 88),
    PackageSpec("world-heritage-identify.apkg", "decks/world-heritage/identify/build/world-heritage-identify.apkg", "world-heritage", 1273, 1273),
    PackageSpec("world-heritage-attributes.apkg", "decks/world-heritage/attributes/build/world-heritage-attributes.apkg", "world-heritage", 1273, 1273),
    PackageSpec("fish-visual.apkg", "decks/fish/visual/build/fish-visual.apkg", "fish", 15, 15),
    PackageSpec("plants-visual.apkg", "decks/plants/visual/build/plants-visual.apkg", "plants", 15, 15),
    PackageSpec("flowers-visual.apkg", "decks/flowers/visual/build/flowers-visual.apkg", "flowers", 15, 15),
    PackageSpec("mushrooms-visual.apkg", "decks/mushrooms/visual/build/mushrooms-visual.apkg", "mushrooms", 15, 15),
)

RELEASE_THEMES = (
    "calendar",
    "countries",
    "constellations",
    "world-heritage",
    "fish",
    "plants",
    "flowers",
    "mushrooms",
)
EXCLUDED_SOURCE_PARTS = {"private", "kitauji", ".git", ".venv", ".yomiyasu"}
MEDIA_SUFFIXES = {".apkg", ".gif", ".jpg", ".jpeg", ".png", ".svg", ".webp"}


def repository_path(relative: str) -> Path:
    path = ROOT / relative
    if not path.is_file() or path.is_symlink():
        raise ReleaseError(f"Required release input is missing or not a regular file: {relative}")
    try:
        path.resolve().relative_to(ROOT)
    except ValueError as error:
        raise ReleaseError(f"Release input resolves outside the repository: {relative}") from error
    return path


def package_attribution_files(theme: str) -> list[tuple[str, Path]]:
    data_dir = ROOT / "decks" / theme / "data"
    sources = sorted(data_dir.glob("*sources.tsv"))
    if not sources:
        raise ReleaseError(f"No source TSV found for theme {theme}")
    files = [
        ("attribution/LICENSE", repository_path("LICENSE")),
        ("attribution/LICENSES.md", repository_path("LICENSES.md")),
    ]
    for source in sources:
        relative = source.relative_to(ROOT).as_posix()
        if not source.is_file() or source.is_symlink():
            raise ReleaseError(f"Theme attribution file is missing or not a regular file: {relative}")
        files.append((f"attribution/data/{source.name}", source))
    assets = data_dir / "assets.tsv"
    if assets.exists():
        relative = assets.relative_to(ROOT).as_posix()
        files.append((f"attribution/data/{assets.name}", repository_path(relative)))
    return files


def model_signatures(model_data: dict) -> dict[str, tuple]:
    """Return merge-relevant notetype signatures keyed by the visible model name."""
    signatures: dict[str, tuple] = {}
    for model in model_data.values():
        name = model.get("name")
        if not name:
            raise ReleaseError("APKG contains a model without a name")
        fields = tuple(field.get("name", "") for field in model.get("flds", []))
        templates = tuple(
            (
                template.get("name", ""),
                template.get("qfmt", ""),
                template.get("afmt", ""),
                template.get("bqfmt", ""),
                template.get("bafmt", ""),
                template.get("bfont", ""),
                template.get("bsize", 0),
            )
            for template in model.get("tmpls", [])
        )
        signature = (fields, templates)
        if name in signatures and signatures[name] != signature:
            raise ReleaseError(f"Model name has conflicting templates within APKG: {name}")
        signatures[name] = signature
    return signatures


def register_release_models(
    release_models: dict[str, tuple[tuple, str]],
    package_models: dict[str, tuple],
    filename: str,
) -> None:
    for model_name, signature in package_models.items():
        previous = release_models.get(model_name)
        if previous is not None and previous[0] != signature:
            raise ReleaseError(
                f"Model name has conflicting field/template signatures across release APKGs: "
                f"{model_name} in {previous[1]} and {filename}"
            )
        release_models[model_name] = (signature, filename)


def validate_apkg(path: Path, expected: PackageSpec, scratch_dir: Path) -> tuple[frozenset[str], set[str], dict[str, tuple]]:
    """Check one APKG's counts and return its GUIDs, media, and model signatures."""
    database = scratch_dir / "release-validation.anki2"
    try:
        with zipfile.ZipFile(path) as archive:
            if "collection.anki2" not in archive.namelist():
                raise ReleaseError(f"APKG has no collection.anki2: {path}")
            database.write_bytes(archive.read("collection.anki2"))
            media_names: set[str] = set()
            if "media" in archive.namelist():
                media_index = json.loads(archive.read("media"))
                media_names = set(media_index.values())
        with sqlite3.connect(database) as connection:
            note_count = connection.execute("select count(*) from notes").fetchone()[0]
            card_count = connection.execute("select count(*) from cards").fetchone()[0]
            guids = [row[0] for row in connection.execute("select guid from notes")]
            models_data = json.loads(connection.execute("select models from col").fetchone()[0])
        signatures = model_signatures(models_data)
    except (OSError, sqlite3.Error, zipfile.BadZipFile, json.JSONDecodeError, KeyError) as error:
        raise ReleaseError(f"Unable to read APKG {path}: {error}") from error
    finally:
        database.unlink(missing_ok=True)

    if (note_count, card_count) != (expected.notes, expected.cards):
        raise ReleaseError(
            f"Unexpected counts in {path.name}: {note_count} notes/{card_count} cards; "
            f"expected {expected.notes}/{expected.cards}"
        )
    if len(guids) != len(set(guids)):
        raise ReleaseError(f"Duplicate note GUIDs within {path.name}")
    return frozenset(guids), media_names, signatures


def validate_asset_manifest(spec: PackageSpec, media_names: set[str]) -> None:
    manifest = ROOT / "decks" / spec.theme / "data" / "assets.tsv"
    if not manifest.exists():
        return
    with manifest.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if not rows or "filename" not in rows[0]:
        raise ReleaseError(f"Asset manifest has no filename entries: {manifest.relative_to(ROOT)}")
    expected_names = {row["filename"] for row in rows if row.get("filename")}
    if expected_names != media_names:
        missing = sorted(expected_names - media_names)
        extra = sorted(media_names - expected_names)
        raise ReleaseError(
            f"APKG media does not match {manifest.relative_to(ROOT)}; "
            f"missing={missing}, extra={extra}"
        )


def add_package_attribution(source: Path, destination: Path, theme: str) -> None:
    shutil.copy2(source, destination)
    attribution = package_attribution_files(theme)
    with zipfile.ZipFile(destination, "a") as archive:
        existing_names = set(archive.namelist())
        for archive_name, file_path in attribution:
            if archive_name in existing_names:
                raise ReleaseError(f"APKG already contains attribution path {archive_name}: {source}")
            info = zipfile.ZipInfo(archive_name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, file_path.read_bytes())


def source_files() -> list[tuple[str, Path]]:
    selected: dict[str, Path] = {}
    fixed = (
        "README.md",
        "LICENSE",
        "LICENSES.md",
        "pyproject.toml",
        "uv.lock",
        "decks/README.md",
    )
    for relative in fixed:
        selected[relative] = repository_path(relative)

    for theme in RELEASE_THEMES:
        theme_root = ROOT / "decks" / theme
        for pattern in ("**/deck.toml", "data/*.tsv"):
            for path in theme_root.glob(pattern):
                if path.is_file() and not path.is_symlink():
                    relative = path.relative_to(ROOT).as_posix()
                    selected[relative] = path

    for base, pattern in ((ROOT / "scripts", "**/*.py"), (ROOT / "tests", "*.py")):
        for path in base.glob(pattern):
            if path.is_file() and not path.is_symlink():
                relative = path.relative_to(ROOT).as_posix()
                selected[relative] = path

    for relative, path in selected.items():
        parts = Path(relative).parts
        if any(part in EXCLUDED_SOURCE_PARTS for part in parts):
            raise ReleaseError(f"Excluded path reached release source manifest: {relative}")
        if Path(relative).suffix.lower() in MEDIA_SUFFIXES or "build" in parts:
            raise ReleaseError(f"Media or generated output reached source manifest: {relative}")
        try:
            path.resolve().relative_to(ROOT)
        except ValueError as error:
            raise ReleaseError(f"Source file resolves outside the repository: {relative}") from error
    return sorted(selected.items())


def write_source_archive(output: Path, files: list[tuple[str, Path]]) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for archive_name, file_path in files:
            info = zipfile.ZipInfo(archive_name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, file_path.read_bytes())


def write_checksums(staging_dir: Path) -> None:
    files = sorted(
        path for path in staging_dir.iterdir()
        if path.is_file() and path.name != CHECKSUM_NAME
    )
    if len(files) != 15:
        raise ReleaseError(f"Expected 15 release assets before SHA256SUMS, found {len(files)}")
    lines = [f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}" for path in files]
    (staging_dir / CHECKSUM_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def verify_staging(staging_dir: Path, source_manifest: list[tuple[str, Path]]) -> None:
    expected_names = set(RELEASE_FILES)
    actual_names = {path.name for path in staging_dir.iterdir() if path.is_file()}
    if actual_names != expected_names:
        raise ReleaseError(f"Staged release file set differs: missing={sorted(expected_names - actual_names)}, "
                           f"unexpected={sorted(actual_names - expected_names)}")
    with zipfile.ZipFile(staging_dir / SOURCE_ZIP_NAME) as archive:
        names = archive.namelist()
        expected_source_names = [name for name, _ in source_manifest]
        if names != expected_source_names:
            raise ReleaseError("Source archive contents do not match the explicit source manifest")
        for name in names:
            parts = Path(name).parts
            if any(part in EXCLUDED_SOURCE_PARTS for part in parts):
                raise ReleaseError(f"Excluded path found in source archive: {name}")
            if Path(name).suffix.lower() in MEDIA_SUFFIXES or "build" in parts:
                raise ReleaseError(f"Media or generated output found in source archive: {name}")

    checksum_lines = (staging_dir / CHECKSUM_NAME).read_text(encoding="utf-8").splitlines()
    if len(checksum_lines) != 15:
        raise ReleaseError(f"Expected 15 SHA256SUMS entries, found {len(checksum_lines)}")
    expected_checksums = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in staging_dir.iterdir() if path.is_file() and path.name != CHECKSUM_NAME}
    parsed: dict[str, str] = {}
    for line in checksum_lines:
        digest, separator, filename = line.partition("  ")
        if not separator or filename in parsed:
            raise ReleaseError(f"Malformed SHA256SUMS line: {line!r}")
        parsed[filename] = digest
    if parsed != expected_checksums:
        raise ReleaseError("SHA256SUMS does not match the staged assets")


def check_output_directory(output: Path) -> bool:
    if not output.exists():
        return False
    if output.is_symlink() or not output.is_dir():
        raise ReleaseError(f"Release output path must be a regular directory: {output}")
    expected = set(RELEASE_FILES)
    existing = list(output.iterdir())
    unexpected = [path.name for path in existing if path.name not in expected]
    non_files = [path.name for path in existing if path.name in expected and (path.is_symlink() or not path.is_file())]
    if unexpected or non_files:
        raise ReleaseError(
            f"Release output contains unexpected files; unexpected={sorted(unexpected)}, "
            f"not_regular_files={sorted(non_files)}"
        )
    return True


def build_release(output: Path) -> tuple[int, int]:
    output = output.expanduser()
    if output.is_symlink():
        raise ReleaseError(f"Release output path cannot be a symlink: {output}")
    output = output.resolve()
    source_paths = [repository_path(spec.source) for spec in PACKAGE_SPECS]
    if len(PACKAGE_SPECS) != 14 or len({spec.filename for spec in PACKAGE_SPECS}) != 14:
        raise ReleaseError("Release package manifest must contain 14 uniquely named APKGs")
    for source in source_paths:
        if output in source.parents or output == source.parent:
            raise ReleaseError(f"Release output would overlap a source package directory: {output}")
    existing_output = check_output_directory(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    source_manifest = source_files()
    total_notes = 0
    total_cards = 0

    with tempfile.TemporaryDirectory(prefix=".anki-release-staging-", dir=output.parent) as temporary:
        staging_dir = Path(temporary) / "release"
        staging_dir.mkdir()
        scratch_dir = Path(temporary) / "scratch"
        scratch_dir.mkdir()
        release_guids: dict[str, str] = {}
        release_models: dict[str, tuple[tuple, str]] = {}

        for spec, source in zip(PACKAGE_SPECS, source_paths, strict=True):
            source_guids, source_media, source_models = validate_apkg(source, spec, scratch_dir)
            validate_asset_manifest(spec, source_media)
            destination = staging_dir / spec.filename
            add_package_attribution(source, destination, spec.theme)
            staged_guids, staged_media, staged_models = validate_apkg(destination, spec, scratch_dir)
            if (staged_guids != source_guids or staged_media != source_media
                    or staged_models != source_models):
                raise ReleaseError(f"Staging changed note identities or package media: {spec.filename}")
            validate_asset_manifest(spec, staged_media)
            for guid in staged_guids:
                previous = release_guids.get(guid)
                if previous is not None:
                    raise ReleaseError(f"Duplicate GUID across release APKGs: {guid} in {previous} and {spec.filename}")
                release_guids[guid] = spec.filename
            register_release_models(release_models, staged_models, spec.filename)
            total_notes += spec.notes
            total_cards += spec.cards
            verify_package_attribution(destination, spec.theme)

        write_source_archive(staging_dir / SOURCE_ZIP_NAME, source_manifest)
        write_checksums(staging_dir)
        verify_staging(staging_dir, source_manifest)

        if existing_output:
            for filename in RELEASE_FILES:
                os.replace(staging_dir / filename, output / filename)
        else:
            os.replace(staging_dir, output)

    return total_notes, total_cards


def verify_package_attribution(path: Path, theme: str) -> None:
    expected = {
        archive_name: file_path.read_bytes()
        for archive_name, file_path in package_attribution_files(theme)
    }
    try:
        with zipfile.ZipFile(path) as archive:
            for name, expected_bytes in expected.items():
                if name not in archive.namelist() or archive.read(name) != expected_bytes:
                    raise ReleaseError(f"APKG attribution is missing or differs from source: {path.name}:{name}")
    except (OSError, zipfile.BadZipFile) as error:
        raise ReleaseError(f"Unable to verify APKG attribution in {path}: {error}") from error


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist/release"),
        help="release staging directory (default: dist/release, relative to the repository root)",
    )
    args = parser.parse_args(argv)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    try:
        notes, cards = build_release(output)
    except (OSError, ReleaseError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Staged 14 APKGs and deck-sources.zip: {notes} notes, {cards} cards -> {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
