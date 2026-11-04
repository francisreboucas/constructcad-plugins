# ConstructCAD plugins

[Português](README.pt-BR.md)

The community index of [ConstructCAD](https://github.com/francisreboucas/constructcad) plugins. A plugin is a folder with a `plugin.toml` manifest and Lua code that adds commands to ConstructCAD. Its commands run like the built-in ones: in the app, with `ccad run`, from scripts and for AI agents over MCP. How to write one is in ConstructCAD's [automation guide](https://github.com/francisreboucas/constructcad/blob/main/docs/automation.md#plugins).

This repository holds no plugin code. Each plugin lives in its author's own repository, and this index lists it: one file per plugin in [`plugins/`](plugins), with where to download each version and its SHA-256 checksum. [`index.json`](index.json) gathers them all for ConstructCAD to read, and is rebuilt automatically when an entry changes:

```
https://raw.githubusercontent.com/francisreboucas/constructcad-plugins/main/index.json
```

## Installing a plugin

Until ConstructCAD's plugin manager reads this index, download a plugin's archive from its entry, check its checksum, unpack it into a folder and load it:

```sh
ccad --plugins /path/to/plugins plugins     # list what loaded
ccad --plugins /path/to/plugins run <plugin>__<command> key=value
```

Plugins run sandboxed: they reach the project only through ConstructCAD's commands, cannot touch files or the network, and have instruction and memory limits. A plugin can import, export or save files only if it asks for the `files` permission. Review a plugin before you install it anyway: the index checks entries, not what plugins do.

## Submitting a plugin

Open a pull request that adds `plugins/<id>.toml`. [CONTRIBUTING.md](CONTRIBUTING.md) describes the entry, the archive and the checks.

## Layout

| | |
|---|---|
| `plugins/<id>.toml` | one entry per plugin, written by its author |
| `index.json` | every entry in one file (generated; do not edit) |
| `scripts/index.py` | checks entries and archives, builds `index.json` (Python 3.11+, standard library only) |
| `tests/` | tests of the checker |

## License

The index (entries, scripts and documentation) is under the [MIT License](LICENSE). Each plugin keeps its own license, given in its entry.
