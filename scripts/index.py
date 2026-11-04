#!/usr/bin/env python3
"""Check the plugin entries and build index.json (standard library only).

    python scripts/index.py check              # check every entry in plugins/
    python scripts/index.py check --download   # also download each archive and check it
    python scripts/index.py build              # write index.json from plugins/
    python scripts/index.py build --check      # fail if index.json is not up to date

The rules for entries and archives are in CONTRIBUTING.md. The manifest rules
mirror ConstructCAD's own loader (crates/cc_lua/src/plugin.rs).
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import tomllib
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
PLUGINS = ROOT / "plugins"
INDEX = ROOT / "index.json"

# The format of index.json; bumped when a reader would misread a new one.
INDEX_FORMAT = 1
# The newest plugin API a released ConstructCAD provides.
MAX_API = 1
KNOWN_PERMISSIONS = {"files"}
MAX_ARCHIVE = 20 * 1024 * 1024
MAX_FILES = 2000
MAX_UNPACKED = 50 * 1024 * 1024

ID = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")
TAG = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
VERSION = re.compile(r"^\d+\.\d+\.\d+([-+][0-9A-Za-z.-]+)?$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
MODULE = re.compile(r"^[A-Za-z0-9_-]+(/[A-Za-z0-9_-]+)*\.lua$")

ENTRY_FIELDS = {"id", "name", "description", "authors", "license", "homepage", "repository", "tags", "versions"}
VERSION_FIELDS = {"version", "api", "url", "sha256", "path", "permissions", "min_app", "notes"}


class Problems:
    def __init__(self) -> None:
        self.items: list[str] = []

    def add(self, where: str, message: str) -> None:
        self.items.append(f"{where}: {message}")


def valid_id(s: object) -> bool:
    return isinstance(s, str) and len(s) <= 32 and bool(ID.match(s))


def is_text(v: object, max_len: int, required: bool = True) -> bool:
    if v is None:
        return not required
    return isinstance(v, str) and (len(v.strip()) > 0 or not required) and len(v) <= max_len


def version_key(v: str) -> tuple:
    core = re.split(r"[-+]", v, maxsplit=1)[0]
    return tuple(int(x) for x in core.split("."))


def check_entry(path: Path, p: Problems) -> dict | None:
    where = f"plugins/{path.name}"
    try:
        entry = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as e:
        p.add(where, f"not valid TOML: {e}")
        return None
    for key in sorted(set(entry) - ENTRY_FIELDS):
        p.add(where, f"unknown field '{key}'")
    pid = entry.get("id")
    if not valid_id(pid):
        p.add(where, "id: up to 32 lowercase letters, digits and single underscores, starting with a letter")
    elif path.stem != pid:
        p.add(where, f"the file must be named {pid}.toml")
    if not is_text(entry.get("name"), 100):
        p.add(where, "name: 1 to 100 characters")
    if not is_text(entry.get("description"), 500):
        p.add(where, "description: 1 to 500 characters")
    authors = entry.get("authors")
    if not (isinstance(authors, list) and authors and all(is_text(a, 100) for a in authors)):
        p.add(where, "authors: a list of names")
    if not is_text(entry.get("license"), 64):
        p.add(where, "license: an SPDX expression, e.g. MIT or GPL-3.0-or-later")
    for key in ("homepage", "repository"):
        url = entry.get(key)
        if key == "repository" and url is None:
            p.add(where, "repository: the plugin's source repository (https)")
        elif url is not None and not (isinstance(url, str) and url.startswith("https://")):
            p.add(where, f"{key}: an https:// URL")
    tags = entry.get("tags", [])
    if not (isinstance(tags, list) and len(tags) <= 8 and all(isinstance(t, str) and TAG.match(t) for t in tags)):
        p.add(where, "tags: up to 8 lowercase words (letters, digits, -)")
    versions = entry.get("versions")
    if not (isinstance(versions, list) and versions):
        p.add(where, "versions: at least one [[versions]] table")
        return entry
    seen: set[str] = set()
    for i, v in enumerate(versions):
        vw = f"{where} [[versions]] #{i + 1}"
        if not isinstance(v, dict):
            p.add(vw, "not a table")
            continue
        for key in sorted(set(v) - VERSION_FIELDS):
            p.add(vw, f"unknown field '{key}'")
        ver = v.get("version")
        if not (isinstance(ver, str) and VERSION.match(ver)):
            p.add(vw, "version: MAJOR.MINOR.PATCH")
        elif ver in seen:
            p.add(vw, f"version {ver} is listed twice")
        else:
            seen.add(ver)
        api = v.get("api")
        if not (isinstance(api, int) and 1 <= api <= MAX_API):
            p.add(vw, f"api: 1 to {MAX_API}")
        url = v.get("url")
        if not (isinstance(url, str) and url.startswith("https://") and url.endswith(".zip")):
            p.add(vw, "url: an https:// link to a .zip file")
        if not (isinstance(v.get("sha256"), str) and SHA256.match(v["sha256"])):
            p.add(vw, "sha256: 64 lowercase hex digits")
        sub = v.get("path")
        if sub is not None and not (isinstance(sub, str) and safe_rel(sub)):
            p.add(vw, "path: a relative folder inside the archive")
        perms = v.get("permissions", [])
        if not (isinstance(perms, list) and all(x in KNOWN_PERMISSIONS for x in perms)):
            p.add(vw, f"permissions: a list of {sorted(KNOWN_PERMISSIONS)}")
        if "min_app" in v and not (isinstance(v["min_app"], str) and VERSION.match(v["min_app"])):
            p.add(vw, "min_app: the oldest ConstructCAD version, MAJOR.MINOR.PATCH")
        if "notes" in v and not is_text(v["notes"], 1000):
            p.add(vw, "notes: up to 1000 characters")
    return entry


def safe_rel(s: str) -> bool:
    parts = PurePosixPath(s).parts
    return bool(parts) and not s.startswith("/") and ":" not in s and all(x not in ("..", ".") for x in parts)


def download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "constructcad-plugins-index"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read(MAX_ARCHIVE + 1)
    if len(data) > MAX_ARCHIVE:
        raise ValueError(f"the archive is larger than {MAX_ARCHIVE} bytes")
    return data


def plugin_root(names: list[str], sub: str | None) -> str:
    """The folder of the archive that holds plugin.toml ('' is the root)."""
    if sub is not None:
        return sub.strip("/") + "/"
    if "plugin.toml" in names:
        return ""
    tops = {n.split("/", 1)[0] for n in names}
    if len(tops) == 1:
        return tops.pop() + "/"
    return ""


def check_archive(entry: dict, v: dict, data: bytes, where: str, p: Problems) -> None:
    digest = hashlib.sha256(data).hexdigest()
    if digest != v.get("sha256"):
        p.add(where, f"sha256 does not match the download ({digest})")
        return
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        p.add(where, "not a zip file")
        return
    infos = z.infolist()
    if len(infos) > MAX_FILES:
        p.add(where, f"more than {MAX_FILES} files")
        return
    if sum(i.file_size for i in infos) > MAX_UNPACKED:
        p.add(where, f"more than {MAX_UNPACKED} bytes unpacked")
        return
    names = [i.filename for i in infos if not i.is_dir()]
    for n in names:
        if not safe_rel(n):
            p.add(where, f"unsafe path in the archive: {n}")
            return
    for i in infos:
        # Symbolic links (Unix mode in the high bits).
        if (i.external_attr >> 16) & 0o170000 == 0o120000:
            p.add(where, f"symbolic link in the archive: {i.filename}")
            return
    root = plugin_root(names, v.get("path"))
    try:
        manifest = tomllib.loads(z.read(root + "plugin.toml").decode("utf-8"))
    except KeyError:
        p.add(where, f"no plugin.toml in '{root or '/'}' of the archive")
        return
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as e:
        p.add(where, f"plugin.toml: {e}")
        return
    if manifest.get("id") != entry.get("id"):
        p.add(where, f"plugin.toml id '{manifest.get('id')}' is not the entry's '{entry.get('id')}'")
    if manifest.get("version") != v.get("version"):
        p.add(where, f"plugin.toml version '{manifest.get('version')}' is not '{v.get('version')}'")
    if manifest.get("api", 1) != v.get("api"):
        p.add(where, f"plugin.toml api {manifest.get('api', 1)} is not {v.get('api')}")
    if sorted(manifest.get("permissions", [])) != sorted(v.get("permissions", [])):
        p.add(where, f"plugin.toml permissions {manifest.get('permissions', [])} differ from the entry's")
    main = manifest.get("main", "main.lua")
    if not (isinstance(main, str) and MODULE.match(main)):
        p.add(where, f"plugin.toml main '{main}' is not a .lua file inside the plugin")
    elif root + main not in names:
        p.add(where, f"{main} is missing from the archive")


def load_entries(p: Problems) -> list[dict]:
    entries = []
    for path in sorted(PLUGINS.glob("*")):
        if path.name.startswith("."):
            continue
        if path.suffix != ".toml":
            p.add(f"plugins/{path.name}", "only <id>.toml files belong in plugins/")
            continue
        entry = check_entry(path, p)
        if entry is not None:
            entries.append(entry)
    return entries


def build_index(entries: list[dict]) -> str:
    plugins = []
    for e in sorted(entries, key=lambda e: e.get("id", "")):
        item = {k: e[k] for k in ("id", "name", "description", "authors", "license", "homepage", "repository") if k in e}
        item["tags"] = e.get("tags", [])
        versions = sorted(e.get("versions", []), key=lambda v: version_key(v["version"]), reverse=True)
        item["versions"] = [{"permissions": [], **v} for v in versions]
        plugins.append(item)
    return json.dumps({"format": INDEX_FORMAT, "plugins": plugins}, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["check", "build"])
    ap.add_argument("--download", action="store_true", help="check: download and check every archive")
    ap.add_argument("--only", nargs="*", default=None, help="check --download: only these plugin ids")
    ap.add_argument("--check", action="store_true", help="build: fail if index.json is not up to date")
    args = ap.parse_args()

    p = Problems()
    entries = load_entries(p)
    if args.action == "check" and args.download and not p.items:
        for e in entries:
            if args.only is not None and e["id"] not in args.only:
                continue
            for v in e["versions"]:
                where = f"{e['id']} {v['version']}"
                try:
                    data = download(v["url"])
                except Exception as err:  # noqa: BLE001 - report any download failure
                    p.add(where, f"download failed: {err}")
                    continue
                check_archive(e, v, data, where, p)
    if p.items:
        print("\n".join(p.items), file=sys.stderr)
        return 1
    if args.action == "build":
        text = build_index(entries)
        if args.check:
            current = INDEX.read_text(encoding="utf-8") if INDEX.exists() else ""
            if current != text:
                print("index.json is out of date: run python scripts/index.py build", file=sys.stderr)
                return 1
        else:
            INDEX.write_text(text, encoding="utf-8", newline="\n")
    print(f"{len(entries)} plugin(s) OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
