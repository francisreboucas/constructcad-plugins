"""Tests of scripts/index.py: entries, archives and the built index.

    python -m unittest discover -s tests
"""

import hashlib
import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import index  # noqa: E402

MANIFEST = 'id = "room_tools"\nname = "Room tools"\nversion = "1.2.0"\napi = 1\n'


def zip_of(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
    return buf.getvalue()


def entry_text(sha: str = "0" * 64, extra: str = "", version_extra: str = "") -> str:
    return f'''id = "room_tools"
name = "Room tools"
description = "Rooms in one step."
authors = ["Someone"]
license = "MIT"
repository = "https://github.com/someone/room_tools"
tags = ["architecture"]
{extra}
[[versions]]
version = "1.2.0"
api = 1
url = "https://github.com/someone/room_tools/releases/download/v1.2.0/room_tools.zip"
sha256 = "{sha}"
{version_extra}
'''


def check_text(text: str, name: str = "room_tools.toml") -> tuple[dict | None, list[str]]:
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / name
        path.write_text(text, encoding="utf-8")
        p = index.Problems()
        return index.check_entry(path, p), p.items


class Entries(unittest.TestCase):
    def test_a_good_entry_passes(self):
        entry, problems = check_text(entry_text())
        self.assertEqual(problems, [])
        self.assertEqual(entry["id"], "room_tools")

    def test_bad_entries_are_reported(self):
        cases = [
            (entry_text(), "other.toml", "named room_tools.toml"),
            (entry_text().replace('id = "room_tools"', 'id = "Room__Tools"'), "room_tools.toml", "id:"),
            (entry_text(extra="color = 1"), "room_tools.toml", "unknown field 'color'"),
            (entry_text().replace("api = 1", "api = 9"), "room_tools.toml", "api:"),
            (entry_text().replace("https://github.com/someone/room_tools/releases", "http://x"), "room_tools.toml", "url:"),
            (entry_text(sha="xyz"), "room_tools.toml", "sha256"),
            (entry_text(version_extra='permissions = ["network"]'), "room_tools.toml", "permissions"),
            (entry_text(version_extra='path = "../up"'), "room_tools.toml", "path:"),
            (entry_text().replace('version = "1.2.0"', 'version = "1.2"'), "room_tools.toml", "version:"),
            (entry_text().replace('tags = ["architecture"]', 'tags = ["Bad Tag"]'), "room_tools.toml", "tags"),
            ("not = [toml", "room_tools.toml", "not valid TOML"),
        ]
        for text, name, expected in cases:
            _, problems = check_text(text, name)
            self.assertTrue(any(expected in x for x in problems), f"{expected!r} not in {problems}")


class Archives(unittest.TestCase):
    def check(self, files: dict[str, str], version_extra: str = "") -> list[str]:
        data = zip_of(files)
        entry, problems = check_text(entry_text(sha=hashlib.sha256(data).hexdigest(), version_extra=version_extra))
        self.assertEqual(problems, [])
        p = index.Problems()
        index.check_archive(entry, entry["versions"][0], data, "t", p)
        return p.items

    def test_a_good_archive_passes(self):
        self.assertEqual(self.check({"plugin.toml": MANIFEST, "main.lua": ""}), [])
        # A single top-level folder (GitHub's archives) or a given path.
        self.assertEqual(self.check({"room_tools-1.2.0/plugin.toml": MANIFEST, "room_tools-1.2.0/main.lua": ""}), [])
        self.assertEqual(
            self.check({"a/plugin.toml": "x", "b/room/plugin.toml": MANIFEST, "b/room/main.lua": ""}, 'path = "b/room"'),
            [],
        )

    def test_bad_archives_are_reported(self):
        cases = [
            ({"main.lua": ""}, "no plugin.toml"),
            ({"plugin.toml": MANIFEST.replace("room_tools", "other"), "main.lua": ""}, "id 'other'"),
            ({"plugin.toml": MANIFEST.replace("1.2.0", "1.3.0"), "main.lua": ""}, "version '1.3.0'"),
            ({"plugin.toml": MANIFEST + 'permissions = ["files"]\n', "main.lua": ""}, "permissions"),
            ({"plugin.toml": MANIFEST}, "main.lua is missing"),
            ({"plugin.toml": MANIFEST, "main.lua": "", "../evil.lua": ""}, "unsafe path"),
        ]
        for files, expected in cases:
            problems = self.check(files)
            self.assertTrue(any(expected in x for x in problems), f"{expected!r} not in {problems}")

    def test_the_checksum_must_match(self):
        data = zip_of({"plugin.toml": MANIFEST, "main.lua": ""})
        entry, _ = check_text(entry_text())
        p = index.Problems()
        index.check_archive(entry, entry["versions"][0], data, "t", p)
        self.assertTrue(any("sha256 does not match" in x for x in p.items))


class Build(unittest.TestCase):
    def test_versions_are_newest_first_with_defaults(self):
        entry, _ = check_text(entry_text())
        old = dict(entry["versions"][0], version="1.10.0")
        entry["versions"].append(old)
        text = index.build_index([entry])
        self.assertIn('"format": 1', text)
        self.assertLess(text.index('"1.10.0"'), text.index('"1.2.0"'))
        self.assertIn('"permissions": []', text)


if __name__ == "__main__":
    unittest.main()
