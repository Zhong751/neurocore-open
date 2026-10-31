# NeuroCore

NeuroCore is an early development foundation for a general AI individual kernel.
The long-term goal is to let an individual develop interests, views and habits
through experience. **This repository does not yet provide a complete AI
individual runtime.** T-01 provides packaging and public-repository safety checks.
T-02 adds a local, source-bound M1 memory core with explicit review and withdrawal;
it does not implement chat, cognition, models or computer control.

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
- `src/neurocore/{core,perception,models,api}/`: importable namespace placeholders.
- `shell-wpf/`: documentation placeholder; no desktop application yet.
- `characters/_template/`: text-only asset policy; no character assets.
- `evals/`: future evaluation boundary; no cognitive benchmark claims.
- `tests/`, `scripts/`, `docs/`: infrastructure verification and delivery evidence.

`src/` keeps repository files separate from the installed Python package and
lets tests check imports from the installed distribution.

## Review and license

T-01 has been independently accepted and merged. T-02 is delivered as a Draft PR
against public `main`, awaiting C2 review. See [T-02 delivery](docs/T02_delivery.md)
and the [Python API and example](docs/T02_api.md). Historical T-01 evidence remains
in [its delivery record](docs/T01_delivery.md). Do not merge without authorization.

Code is licensed under [Apache License 2.0](LICENSE). Tool and Action licenses
and their pinned sources are recorded in [dependencies](docs/dependencies.md).
