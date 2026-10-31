# NeuroCore

NeuroCore is an early development foundation for a general AI individual kernel.
The long-term goal is to let an individual develop interests, views and habits
through experience. **This repository does not yet provide a complete AI
individual runtime.** T-01 provides packaging and public-repository safety checks.
T-02 adds a local, source-bound M1 memory core with explicit review and withdrawal.
T-03 adds character seeds, persistent independent identities and read-only
diagnostics. It does not implement chat, cognition, models or computer control.

This public project starts with independent Git history. It contains no imported
private Git history, user instance, conversation, credential or character art.
M1 policy provenance and the independent public adaptation are recorded in
[T-02 sources](docs/T02_sources.md).

## Development

Use Python **3.12** and uv **0.13.6**. Runtime dependencies are empty; tests use
Python's standard library. See [official uv installation instructions](https://docs.astral.sh/uv/getting-started/installation/).

```powershell
uv sync --locked
uv run --no-sync python -I -c "import neurocore; import neurocore.core, neurocore.perception, neurocore.models, neurocore.api"
uv run --no-sync python -m unittest discover -s tests -v
uv run --no-sync python scripts/check_sensitive.py
uv build
```

The scanner reads Git-index blobs, so stage intended changes before the final
pre-push scan. It reports index-entry numbers and rule names, never raw paths.
Its scope and limitations are in [security checks](docs/security_checks.md).

## Layout

- `src/neurocore/memory/`: M1 writer and strictly read-only source/reference APIs.
- `src/neurocore/characters.py`, `instances.py`, `doctor.py`: seed snapshots,
  identity creation/loading and strictly read-only file diagnostics.
- `src/neurocore/{core,perception,models,api}/`: importable namespace placeholders.
- `shell-wpf/`: documentation placeholder; no desktop application yet.
- `characters/_template/`: blank text-only character package; no official persona or art.
- `evals/`: future evaluation boundary; no cognitive benchmark claims.
- `tests/`, `scripts/`, `docs/`: infrastructure verification and delivery evidence.

`src/` keeps repository files separate from the installed Python package and
lets tests check imports from the installed distribution.

## Review and license

T-01 and T-02 have been independently accepted and merged. T-03 is developed
directly from public `main` for a Draft PR and C2 review. See the
[T-03 contract](docs/T03_api.md), [seed guide](docs/seed_guide.md) and
[delivery record](docs/T03_delivery.md). Historical evidence remains in
[T-01](docs/T01_delivery.md) and [T-02](docs/T02_delivery.md); the
[M1 Python API](docs/T02_api.md) remains available. Do not merge without authorization.

Code is licensed under [Apache License 2.0](LICENSE). Tool and Action licenses
and their pinned sources are recorded in [dependencies](docs/dependencies.md).

## Create an instance

Copy `characters/_template/` to a local directory and fill its seed using the
[guide](docs/seed_guide.md). A seed is initial guidance, not historical evidence
or an immutable personality. Images are optional and supplied by the user.

```powershell
uv run --no-sync neurocore doctor --character "characters/_template"
uv run --no-sync neurocore new --character "characters/_template"
# Or choose a fresh directory whose parent already exists:
uv run --no-sync neurocore new --character "characters/_template" --instance "instances/sample"
uv run --no-sync neurocore doctor --instance "instances/sample"
```

Each call creates a new identity, a private seed snapshot and an empty M1 store.
Existing targets are refused. Doctor reports PASS/WARN/FAIL without modifying
the target; it does not connect to a model. In a character or instance directory,
`neurocore doctor` checks that directory. Python module usage is also supported:
`python -m neurocore doctor --character "characters/_template"`.
