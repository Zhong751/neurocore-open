# T-03: character and instance contract, version 1

## Character package

The caller explicitly selects a local directory containing `character.json`:

```json
{
  "format_version": 1,
  "name": "Synthetic Example",
  "seed": "seed.md",
  "assets": ["assets/optional-portrait.png"]
}
```

`format_version`, `name` and `seed` are required; `assets` defaults to `[]`.
Unknown or duplicate fields, malformed JSON, non-object JSON, invalid UTF-8,
non-finite numbers and unsupported versions fail with distinct diagnostics.
The version must be the integer 1, not a boolean. Name is nonblank text of at
most 100 characters without control characters. Seed is a nonempty UTF-8 `.md`
file without NUL. Headings are guidance, not a machine-enforced personality.

The manifest is at most 64 KiB, seed 256 KiB, assets 16 files / 8 MiB each, and
total loaded bytes 32 MiB. Assets are optional: absent paths produce WARN and
are not copied. Files explicitly referenced but unreadable or unsafe produce
FAIL. Only the manifest, seed and listed existing assets are read and copied;
unlisted files are not recursively discovered. No asset is rendered/executed.

References use `/`-separated relative paths, at most 240 characters. Absolute,
drive/UNC, parent traversal, backslashes, empty/dot components, Windows device
names, alternate streams, forbidden Windows characters, trailing dots/spaces,
case-insensitive duplicates and file/directory overlaps are rejected. Linked,
junction/reparse and hard-linked input files are rejected, including links
inside the selected root. Explicit root paths may be absolute or relative,
but cannot contain `..` or linked ancestors. These controls run with the host
user's permissions; they do not grant additional OS access rights.

## CLI

```text
neurocore new --character DIRECTORY [--instance NEW_DIRECTORY]
neurocore doctor [--character DIRECTORY | --instance DIRECTORY]
python -m neurocore ...
```

`new` defaults to `./instances/<new UUID>`, creating the `instances` parent when
needed. An explicit destination requires an existing parent. Names/seed text
never choose a destination. Existing destinations, even empty directories, are
refused. Success prints JSON with `instance_id` and absolute
`instance_directory`. Exit codes: 0 success, 1 validation/I/O failure,
2 invalid CLI arguments. There is no overwrite, delete or repair option.

Doctor with no target checks only the current directory: `instance.json` has
priority over `character.json`; neither present yields FAIL. It never scans for
other instances. Every result line is `PASS|WARN|FAIL check_name: message`.
Exit 0 means no FAIL (WARN is allowed), 1 means at least one FAIL, and 2 means
invalid arguments. Missing optional art is a WARN, not a creation failure.
Diagnostics identify invalid JSON, fields, version, paths, snapshot, schema or
authority without printing seed/asset/database content. Checks dependent on a
failed prerequisite stop; no PASS is claimed for unperformed checks.

## Identity and creation

```text
NEW_DIRECTORY/
  instance.json
  character/character.json
  character/<seed and present declared assets>
  memory/memory.sqlite3
```

`instance.json` has exactly `format_version: 1`, `instance_id` (canonical UUID
hex), `created_at` (timezone-aware ISO timestamp), `character_hashes` (relative
path to SHA-256 map of all copied files), and `memory_store_id` (UUID hex).
Snapshot and memory locations are fixed; manifests cannot redirect database
access to another directory. M1 `brain_id` equals `instance_id`; the independently
generated M1 `store_id` must also match the manifest. Reloading preserves both.

Creation validates the source before reserving a fresh directory via exclusive
`mkdir`. It copies bytes already validated, creates an empty M1 using its
existing explicit API, verifies the snapshot and storage, then flushes and
atomically renames a pending manifest to `instance.json` **last**. No seed,
example dialogue or made-up experience is inserted into M1. Concurrent creators
of the same target cannot both reserve it.

If creation fails after reservation, its incomplete target is deliberately
retained, never silently deleted or reused. Missing/invalid completion metadata,
snapshot or database is FAIL and cannot be loaded as a complete instance. The
caller may inspect the directory and choose a new destination. This is a
process-failure boundary, not a guarantee against physical disk/power failure.

Source-package edits cannot change the snapshot; changing copied bytes fails
hash verification. Hashes detect changes relative to the manifest, not malicious
rewriting of both by someone with write access. Copying an entire instance is
not a supported way to create a new identity; use `new`. Seed preservation is
not a claim that future personality cannot grow.

## Python API and read-only boundary

```python
from neurocore.characters import load_character
from neurocore.instances import create_instance, load_instance
from neurocore.doctor import check_character, check_instance

package = load_character("characters/_template")
instance = create_instance(package.root)  # explicit creation
same = load_instance(instance.root)      # no initialization or recovery
reader = same.reader()
writer = same.writer()                  # explicit M1 write capability
checks = check_instance(instance.root)
```

`CharacterPackage` exposes `root`, `name`, `seed`, an immutable `files` mapping
of relative paths to bytes, and `missing_assets`. `Instance` exposes `root`,
`instance_id`, `created_at`, `character`, `memory_store_id`, `memory_directory`,
`reader()` and `writer()`. `CharacterError` and `InstanceError` derive from
`ValueError`. Checks expose `status`, `name`, `message`. M1's API is unchanged.

Doctor and `load_instance` never call `MemoryStore`, open the source through
SQLite, initialize an on-disk database, recover logs, change records or advance
an epoch/cursor. They read bounded regular-file bytes, reject SQLite WAL header
or any `-journal`/`-wal`/`-shm`, and parse the snapshot in RAM with `deserialize`.
They check exact M1 schema, SQLite `quick_check`, foreign keys and identity/store
authority. Before/after file metadata and sidecars detect ordinary concurrent
changes; busy state fails closed and callers may retry once an explicit writer
has closed. The database inspection limit is 256 MiB. Model connection checks
are excluded. This is structural/authority inspection, not a full semantic
re-audit of every M1 fact or proof against concurrent hostile filesystem edits.
Filesystem access timestamps may be updated by the OS when any file is read;
doctor itself does not write files, file modification times or persistent state.

WAL and recovery states require separate explicit owner/writer handling;
doctor does not repair them. Normal T-03-created M1 stores use rollback mode.
The existing T-02 `MemoryReader` remains a separate API with its original
contract; doctor uses byte inspection specifically to avoid SQLite side effects.
