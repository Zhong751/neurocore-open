# T-03: character packages, instances and read-only doctor

Status: implemented for Draft PR / C2 independent review; not authorization to
merge, publish a release or begin T-04. Base is public `main`, fetched and checked
before development: `7a544c59dfa966031ed64881ef8d2850cdafcb88`.
Branch: `codex/t03-character-instances`. No private or unmerged PR is a parent.

## Delivered

- Version 1 `character.json` and UTF-8 Markdown seed loading with explicit
  errors, optional assets, an empty public template and a seed-writing guide.
- `neurocore new --character ... [--instance ...]`: independent persistent
  UUIDs, distinct M1 store IDs, byte snapshots and completion metadata written
  last. Existing/failed destinations are never overwritten or silently deleted.
- `neurocore doctor [--character ... | --instance ...]`: PASS/WARN/FAIL and
  documented exit codes, bounded file reads and in-memory SQLite inspection.
  Missing paths never initialize a database; WAL/recovery state fails closed.
- Stable Python APIs and installed console/module CLI, with Windows Chinese
  and space paths, independent subprocess loading and creation contention tests.

Seeds and fictional demonstrations never become M1 events. The source package
cannot rewrite an instance snapshot. No formal Zealor voice/art, model connection,
dialogue generation, cognitive growth, desktop/control/social integration,
private Brain migration or release is included. All test data is synthetic.
Runtime dependencies, lockfile, license, Action pins and M1 source are unchanged.

## Acceptance evidence

Environment: Windows, Python 3.12.16, uv 0.13.6. The 60 baseline tests remain
unchanged; 26 T-03 tests are added in `tests/test_instances.py`.

| Requirement | Verification |
| --- | --- |
| 1. Same package, two independent instances | Different persistent UUIDs, store IDs and directories |
| 2. Separate M1 events, no cross reads | Both write the same event ID with different contents; foreign references fail |
| 3. Cross-process identity and memory | Actual isolated Python subprocess reloads both IDs and stored event |
| 4. JSON/fields/version diagnostics | Distinct `character-json`, `character-fields`, `character-version` cases |
| 5. Optional images absent | Both no references and missing declared image produce WARN and create successfully |
| 6. Existing destination unchanged | Existing empty directory, occupied directory, file and instance refused; bytes preserved |
| 7. Interrupted creation incomplete | Injected failure before M1 creation leaves no completion manifest; load/doctor fail |
| 8. Paths and links bounded | Traversal/absolute/drive/UNC/ADS/device names, real Windows junction and hard links rejected |
| 9. Strictly read-only doctor | Inventory, byte hashes, mtimes, logical DB dump, data_version and epoch unchanged; missing/corrupt/WAL/sidecar cases |
| 10. Chinese and spaces on Windows | CLI creates and inspects an instance at both kinds of path; identity/event reload correctly |
| 11. Baseline regression suite | Full suite result recorded below |
| 12. CI/lock/scan/build/wheel | Validation results and public runner link recorded below |

The tests also cover source edits, empty initial M1, exact snapshot hashes,
same-brain replacement store rejection, CLI default target selection, invalid
argument exit codes and two real competing creation processes. Independent
local review additionally verified broken foreign keys, absent asset parent
directories, a journal path that is a directory and malformed Unicode paths.

## Validation results

| Check | Actual result |
| --- | --- |
| Locked sync / `uv lock --check` | Passed offline; lockfile unchanged |
| Installed isolated imports | Passed, including new T-03 modules |
| T-03 focused unittest suite | 26 passed, zero skipped, 8.999 seconds |
| Full unittest suite | 86 passed (60 baseline + 26 T-03), zero skipped, 35.436 seconds |
| sdist and wheel build | Passed |
| Fresh wheel environment, Python `-I` | Imports/license/M1 lifecycle, installed CLI creation and read-only doctor passed outside checkout |
| Staged Git-index sensitive scan | Passed; all tracked/index blobs checked, with public diff review |
| Public Windows CI | Pending Draft PR run; local success is not runner success |

Reproduce with the README development commands. The workflow runs all tests,
locked sync/check, installed imports, Git-index scan, sdist/wheel build and
`scripts/check_distribution.py` in an independent wheel environment.

## Failures found and corrected

The first T-03 run failed because Python 3.12 on Windows can report different
`ctime` values through `stat` and `fstat` for an unchanged file. The code now
compares device/inode, size and modification time across those APIs. Accurate
diagnostic tests also ensure input failures are not masked by a file-change
error. A follow-up test failure was the synthetic fixture's default CRLF versus
the expected LF; the fixture explicitly writes LF and the product still copies
exact bytes. Both issues were fixed before the successful focused run.

An earlier independent probe demonstrated that existing M1 `mode=ro` alone can
create WAL sidecars, and that authority-only checks miss absent tables. T-03
therefore reads database bytes into RAM, checks full schema and foreign keys,
and never lets SQLite open the source file. M1 implementation was not rewritten.

## Public change scope

```text
.github/workflows/ci.yml
AGENTS.md
README.md
characters/_template/README.md
characters/_template/character.json
characters/_template/seed.md
docs/seed_guide.md
docs/T03_api.md
docs/T03_delivery.md
pyproject.toml
scripts/check_distribution.py
src/neurocore/__main__.py
src/neurocore/_files.py
src/neurocore/_memory_check.py
src/neurocore/characters.py
src/neurocore/cli.py
src/neurocore/doctor.py
src/neurocore/instances.py
tests/test_instances.py
```

All public changes are newly written code, text or synthetic tests. No binary
asset, user instance, conversation, credential or private repository content is
staged. The scanner is a limited pattern/path check, supplemented by review of
the full diff; it is not a privacy proof. Generated build environments are local.

## Known limits

- Incomplete creations are retained for inspection and refused on retry; there
  is no automated deletion/repair or physical power-loss certification.
- Doctor is structural/authority validation, not semantic re-review of every
  M1 fact. SQLite snapshots are limited to 256 MiB; WAL and any journal/sidecar
  are refused rather than recovered. Busy files may require an idle retry.
- Hashes detect snapshot changes relative to metadata, not an attacker rewriting
  the complete instance. Filesystem checks do not establish a security boundary
  against a concurrent hostile process with permission to replace the roots.
- The OS may update read-access timestamps. Doctor writes no target content,
  modification timestamps, database records, recovery files or durable cursors.
- Existing T-02 MemoryReader behavior is unchanged. T-03 strict read-only
  inspection is deliberately separate. No model/backend compatibility is tested.

These limits and the precise formats are documented in [T-03 API](T03_api.md).
