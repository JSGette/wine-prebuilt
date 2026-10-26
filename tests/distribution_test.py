"""Distribution contracts, using real compression and archive readers."""

import gzip
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from package import archive, verify_archive_pair
from distribution import FORMATS, PLATFORMS, basename, serial_from_tag, sha256
from fetch import ROOT
from release import compare_existing, validate_assets
import recipe


class ArchivesTest(unittest.TestCase):
    def test_both_formats_contain_the_same_tar_with_executable_and_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload = root / "payload"
            (payload / "bin").mkdir(parents=True)
            (payload / "bin/wine").write_bytes(b"fixture executable\n")
            (payload / "bin/wine").chmod(0o755)
            (payload / "bin/wine64").symlink_to("wine")
            output = root / "wine-linux-amd64-11.20.1.tar.gz"
            archive(output, [(payload, ".")])
            zstd = root / "wine-linux-amd64-11.20.1.tar.zst"
            self.assertTrue(zstd.is_file(), "the distribution must provide zstd as well as gzip")
            self.assertEqual(gzip.decompress(output.read_bytes()),
                             subprocess.check_output(["zstd", "-dc", str(zstd)]))
            with tarfile.open(output) as contents:
                self.assertEqual(contents.getmember("./bin/wine").mode, 0o755)
                self.assertEqual(contents.getmember("./bin/wine64").linkname, "wine")
                self.assertEqual(contents.getmember("./bin/wine").mtime, 0)
            with self.assertRaises(FileExistsError):
                archive(output, [(payload, ".")])

    def test_different_compressed_payload_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "wine.tar.gz"
            with gzip.open(output, "wb") as stream:
                stream.write(b"original")
            (root / "wine.tar.zst").write_bytes(subprocess.check_output(["zstd", "-qc"], input=b"changed"))
            with self.assertRaisesRegex(ValueError, "different tar streams"):
                verify_archive_pair(output)


class ReleaseTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name)
        # Small stand-ins for archive bytes exercise release completeness and
        # hash binding; actual tar/compression behavior is tested above.
        for platform, spec in PLATFORMS.items():
            name = basename(platform, "11.20", 1)
            archives = {}
            for kind in ("", "-sources"):
                for extension in FORMATS:
                    path = self.output / (name + kind + extension)
                    path.write_bytes(b"release bytes")
                    digest = sha256(path)
                    (self.output / (path.name + ".sha256")).write_text(f"{digest}  {path.name}\n")
                    if not kind:
                        archives[path.name] = digest
            self.write_json(name + ".manifest.json", {"platform": platform, "wine": "11.20",
                            "artifact_version": "11.20.1", "recipe_sha256": recipe.digest(ROOT)})
            self.write_json(name + ".qualification.json", {"status": "passed", "archives": archives,
                            "guests": spec["guests"]})
            (self.output / (name + ".attestation.jsonl")).write_text("verified separately by gh\n")
            if platform.startswith("linux-"):
                self.write_json(name + ".tar.gz.glibc217.json", {"status": "passed",
                                "artifact": name + ".tar.gz", "sha256": archives[name + ".tar.gz"]})

    def write_json(self, name, value):
        (self.output / name).write_text(json.dumps(value))

    def test_complete_three_executor_release_is_accepted(self):
        assets = validate_assets(self.output, "11.20", 1)
        self.assertEqual(len(assets), 35)

    def test_modified_archive_is_rejected_before_upload(self):
        (self.output / "wine-linux-amd64-11.20.1.tar.gz").write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            validate_assets(self.output, "11.20", 1)

    def test_missing_attestation_is_rejected_before_upload(self):
        (self.output / "wine-macos-arm64-11.20.1.attestation.jsonl").unlink()
        with self.assertRaises(FileNotFoundError):
            validate_assets(self.output, "11.20", 1)

    def test_qualification_for_another_archive_is_rejected(self):
        name = "wine-linux-arm64-11.20.1.qualification.json"
        report = json.loads((self.output / name).read_text())
        report["archives"]["wine-linux-arm64-11.20.1.tar.gz"] = "0" * 64
        self.write_json(name, report)
        with self.assertRaisesRegex(ValueError, "not qualified"):
            validate_assets(self.output, "11.20", 1)

    def test_conflicting_published_asset_cannot_be_overwritten(self):
        path = self.output / "wine-linux-amd64-11.20.1.tar.gz"
        compare_existing(path, "sha256:" + sha256(path))
        with self.assertRaisesRegex(ValueError, "conflicting release asset"):
            compare_existing(path, "sha256:" + "0" * 64)

    def test_tag_keeps_wine_version_separate_from_serial(self):
        self.assertEqual(serial_from_tag("11.20.0", "11.20"), 0)
        self.assertEqual(serial_from_tag("11.0.1.2", "11.0.1"), 2)
        with self.assertRaises(ValueError):
            serial_from_tag("11.21.1", "11.20")
        with self.assertRaises(ValueError):
            serial_from_tag("11.20.01", "11.20")


if __name__ == "__main__":
    unittest.main()
