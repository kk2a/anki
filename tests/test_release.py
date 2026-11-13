"""Tests for the safe public release staging command."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_release  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ReleaseTests(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.temp_root = Path(self.temp.name)

    def test_stages_all_public_packages_and_source_manifests(self):
        source_hashes = {
            spec.source: sha256(ROOT / spec.source)
            for spec in build_release.PACKAGE_SPECS
        }
        output = self.temp_root / "release"
        self.assertEqual(build_release.build_release(output), (3505, 3728))
        expected_names = set(build_release.RELEASE_FILES)
        self.assertEqual({path.name for path in output.iterdir()}, expected_names)
        self.assertEqual(len(list(output.glob("*.apkg"))), 14)

        checksum_entries = {}
        for line in (output / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
            digest, separator, filename = line.partition("  ")
            self.assertTrue(separator)
            self.assertNotIn(filename, checksum_entries)
            checksum_entries[filename] = digest
        self.assertEqual(set(checksum_entries), expected_names - {"SHA256SUMS"})
        for filename, digest in checksum_entries.items():
            self.assertEqual(sha256(output / filename), digest)

        with zipfile.ZipFile(output / build_release.SOURCE_ZIP_NAME) as archive:
            source_names = archive.namelist()
            expected_source_names = [name for name, _ in build_release.source_files()]
            self.assertEqual(source_names, expected_source_names)
            for name in source_names:
                parts = Path(name).parts
                self.assertFalse(set(parts) & build_release.EXCLUDED_SOURCE_PARTS, name)
                self.assertNotIn("build", parts, name)
                self.assertNotIn("assets", parts, name)
                self.assertNotIn(Path(name).suffix.lower(), build_release.MEDIA_SUFFIXES, name)

        guids: dict[str, str] = {}
        scratch = self.temp_root / "scratch"
        scratch.mkdir()
        for spec in build_release.PACKAGE_SPECS:
            staged = output / spec.filename
            found_guids, media, signatures = build_release.validate_apkg(staged, spec, scratch)
            build_release.validate_asset_manifest(spec, media)
            for guid in found_guids:
                self.assertNotIn(guid, guids, f"{spec.filename} overlaps {guids.get(guid)}")
                guids[guid] = spec.filename
            self.assertTrue(signatures)
            build_release.verify_package_attribution(staged, spec.theme)

        self.assertEqual(len(guids), 3505)
        for source, digest in source_hashes.items():
            self.assertEqual(sha256(ROOT / source), digest, f"source package changed: {source}")

    def test_existing_output_with_unexpected_file_is_left_untouched(self):
        output = self.temp_root / "release"
        output.mkdir()
        unexpected = output / "notes.txt"
        unexpected.write_text("keep", encoding="utf-8")

        with self.assertRaisesRegex(build_release.ReleaseError, "unexpected files"):
            build_release.build_release(output)

        self.assertEqual(unexpected.read_text(encoding="utf-8"), "keep")
        self.assertEqual({path.name for path in output.iterdir()}, {"notes.txt"})


if __name__ == "__main__":
    unittest.main()
