# Submitting a plugin

1. Publish your plugin in its own public repository, with a license.
2. For each version, attach a `.zip` of the plugin to a release of that repository, as a release asset.
3. Open a pull request here that adds (or updates) `plugins/<id>.toml`.

The checks below run on every pull request. A maintainer also reads the plugin's code before merging, and may decline plugins that are misleading, harmful or not about ConstructCAD.

## The entry

`plugins/<id>.toml`, named after the plugin's `id`:

```toml
id = "quick_rooms"                    # the id in your plugin.toml
name = "Quick rooms"
description = "Rectangular rooms in one step, and wall totals by type."
authors = ["Your Name"]
license = "MIT"                       # SPDX, as in your repository
repository = "https://github.com/you/quick_rooms"
homepage = "https://you.example/quick_rooms"   # optional
tags = ["architecture", "rooms"]               # optional, up to 8

[[versions]]
version = "0.1.0"                     # the version in your plugin.toml
api = 1                               # the api in your plugin.toml
url = "https://github.com/you/quick_rooms/releases/download/v0.1.0/quick_rooms.zip"
sha256 = "…"                          # sha256sum quick_rooms.zip
permissions = []                      # the permissions in your plugin.toml
path = "quick_rooms"                  # optional: the folder of plugin.toml in the zip
min_app = "0.10.0"                    # optional: the oldest ConstructCAD it works with
notes = "First release."              # optional
```

Add a new `[[versions]]` table for each release and keep the older ones; ConstructCAD offers the newest one its plugin API supports.

## The archive

- A `.zip` uploaded as a **release asset**. GitHub's automatic "Source code" archives are not guaranteed to keep the same bytes, so their checksum can change.
- `plugin.toml` sits at the root of the zip, in its single top-level folder, or in the folder given by `path`.
- Its `id`, `version`, `api` and `permissions` match the entry, and its `main` file (`main.lua` by default) is there.
- At most 20 MB, 2000 files and 50 MB unpacked; no absolute paths, `..` or symbolic links.
- A published version never changes: to fix it, release a new version.

## Checking locally

With Python 3.11 or newer:

```sh
python scripts/index.py check                                   # the entries
python scripts/index.py check --download --only quick_rooms     # your archives
python -m unittest discover -s tests                            # the checker's tests
```

You do not need to edit `index.json`: it is rebuilt when the pull request is merged.

## Permissions

`files` lets a plugin run ConstructCAD's commands that read or write files (import, export, save). Ask for it only if the plugin needs it, and say why in its description. Plugins never get network access.
