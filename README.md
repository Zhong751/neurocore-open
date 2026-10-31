# NeuroCore

NeuroCore is an early development foundation for a general AI individual kernel.
The long-term goal is to let an individual develop interests, views and habits
through experience. **This repository does not yet provide a complete AI
individual runtime.** T-01 contains packaging, tests and public-repository safety
checks only; it does not implement chat, memory, cognition or computer control.

This public project starts with independent Git history. It contains no imported
private implementation, user instance, conversation, credential or character art.

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
pre-push scan. It reports rule names and paths without echoing matched values.
Its scope and limitations are in [security checks](docs/security_checks.md).

## Layout

- `src/neurocore/{core,perception,models,api}/`: importable namespace placeholders.
- `shell-wpf/`: documentation placeholder; no desktop application yet.
- `characters/_template/`: text-only asset policy; no character assets.
- `evals/`: future evaluation boundary; no cognitive benchmark claims.
- `tests/`, `scripts/`, `docs/`: infrastructure verification and delivery evidence.

`src/` keeps repository files separate from the installed Python package and
lets tests check imports from the installed distribution.

## Review and license

T-01 is delivered as a draft PR against public `main`. See the
[delivery record](docs/T01_delivery.md) for actual results and outstanding limits.
Subsequent functionality requires independent C2 acceptance before merging.

Code is licensed under [Apache License 2.0](LICENSE). Tool and Action licenses
and their pinned sources are recorded in [dependencies](docs/dependencies.md).
