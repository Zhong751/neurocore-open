# T-02: trusted memory core delivery

Status: implemented and locally self-tested; Draft PR awaits C2 independent
review. Do not merge or start T-03. Public base:
`fb06c6dd320c8e386264e0b390a6beceb5936137`; branch `codex/t02-m1-core`.
No private commits are parents of this branch.

## Delivered

- `neurocore.memory/1`: standalone Python writer and strictly read-only reader.
- One explicit instance directory / one SQLite authority; durable event identity,
  source and speaker, immutable original payload, status, version and epoch.
- Pending proposals, explicit review, preserved reviewed-inference exclusion,
  corrections, withdrawal, exact predicate conflict exclusion and suppression.
- Exact source spans and versioned references; dependencies bind parent revisions.
  Transactional source withdrawal and transitive invalidation, including after
  restart. Invalid audit records remain inspectable but cannot be valid facts.
- Read-only connections use `mode=ro`, `query_only` and a SQL authorizer; queries
  never initialize a store, modify caches or schedule jobs. Snapshot results are
  checked against a fresh epoch before returning.
- A functioning [synthetic example](../examples/m1_lifecycle.py),
  [Python contract](T02_api.md), [source/license allowlist](T02_sources.md).

No third-party runtime/test/build dependency is added. No old source file or
private history is copied; the bounded public adaptation preserves the inspected
M1 policies without the private import/archive/tokenizer/model stack. The private
M1 package has no standalone license grant, so unspecified code is not copied or
relicensed. No private Brain, conversation, API/model setting, backup, runtime
log or business-data fixture is read or imported. All test/example content is
clearly synthetic and newly constructed.

## Validation and counterexamples

Local Windows, Python 3.12.16, uv 0.13.6:

| Check | Actual result |
| --- | --- |
| Locked environment and lock consistency | Passed offline, only local package |
| Existing T-01 plus M1 `unittest discover` | 59 passed, zero skipped, 24.982 seconds |
| Source/runtime import and synthetic example | Passed without model/key |
| sdist then wheel build | Passed, unchanged uv backend and lock |
| Separate wheel environment, Python `-I` | Imports, license and actual M1 confirm/withdraw lifecycle passed |
| Public Windows Actions | Pending actual runner; final SHA/run result must be verified in the Draft PR before delivery is called complete |

The 23 new M1 tests cover the following. Counts are not a claim of full formal
verification, and the old 36 T-01 tests remain intact.

| Task scenario / counterexample | Evidence |
| --- | --- |
| Raw event saved and restart-queryable | `test_event_survives_real_interpreter_restart_and_missing_open_is_read_only`; actual isolated Python subprocess |
| No source / no supports / forged quote | Rejected without confirmed facts in `test_no_support_invalid_quote_and_stale_proposal_are_rejected` |
| AI/user-source laundering and wrong speaker | Direct, reported, mixed-support and reviewed-inference cases in both new test modules |
| Confirm then correct | New source and pending revision, old ref/descendant invalid; subsequent explicit confirmation and reopen succeed |
| Source withdrawal | Three-level dependency chain; direct and transitive results remain withdrawn in a new interpreter |
| Repeated withdrawal | No extra epoch/audit; two actual competing Python processes commit only one withdrawal |
| Source integrity/reference validity | Tampered active payload, stale epoch, foreign authority, missing dependency index rejected |
| Instance isolation | Different stores, including identical brain labels and colliding event IDs, cannot reuse references |
| Read-only | SQL denial plus observer `data_version`, full logical dump and directory inventory unchanged; legitimate external write separately observed |
| Transaction failure | Fault injected after invalidation rolls the source/fact changes and epoch back together |
| Abrupt process exit | Real `os._exit(23)` during a spilling uncommitted SQLite write; explicit writer open recovers the prior committed state |
| Wrong identity/version and existing file | Fail closed; no overwrite, new identity or silent migration |
| Original T-01 safety/build | Original scanner assertions retained; no scanner rule, permission, dependency pin or license relaxation |

The fault-injection test is distinct from the real process-exit test. Neither
claims physical power-loss or arbitrary disk-corruption certification. A repeat
confirmation is deliberately revision-CAS rather than a universal idempotency
operation; callers inspect durable state on conflict. No test uses a live model.

## Public file review and publication boundary

Only these task paths may be staged:

```text
.github/workflows/ci.yml
AGENTS.md
README.md
docs/T02_api.md
docs/T02_delivery.md
docs/T02_sources.md
examples/m1_lifecycle.py
scripts/check_distribution.py
src/neurocore/memory/__init__.py
src/neurocore/memory/_reader.py
src/neurocore/memory/_storage.py
src/neurocore/memory/_writer.py
tests/test_memory.py
tests/test_memory_boundaries.py
tests/test_package.py
```

The pre-push gate reviews all these file contents and the complete Git-index
sensitive scan, checks the diff for private paths/data/credentials, verifies no
unexpected file or private parent history, and builds the distribution. Runtime
test directories, wheels, logs and audit working files are not staged. Pattern
scanning is not a proof against arbitrary private prose; per-file inspection is
required. Generic Git authentication may be handled by the configured Git client;
no model key or private application credential is read.

## Reproduce from the public branch

```powershell
uv sync --locked
uv lock --check
uv run --no-sync python -I -c "import neurocore.memory"
uv run --no-sync python -m unittest discover -s tests -v
uv run --no-sync python -I examples/m1_lifecycle.py
uv run --no-sync python scripts/check_sensitive.py
uv build
uv venv .wheel-venv --python 3.12
uv pip install --python .wheel-venv/Scripts/python.exe --no-deps (Get-ChildItem dist -Filter '*.whl').FullName
& ./.wheel-venv/Scripts/python.exe -I scripts/check_distribution.py
```

For focused C2 verification:
`uv run --no-sync python -m unittest discover -s tests -p 'test_memory*.py' -v`.
Review the fact-status versus review-status mapping, exact source qualification,
parent traversal, atomic write boundary and read-only SQL boundary. Public base
is main, not any private or unmerged PR.

## Failures, limits and exclusions

- Initial host Git command refused this sandbox-owned checkout. A per-command
  `safe.directory` for this exact public checkout resolved it; no global Git
  trust setting changed. The first uv invocation hit the inaccessible default
  cache; using the pre-existing task-local cache succeeded offline.
- Private M1 tests are used as policy references, not run in a private instance.
  This is a small independent public schema, not binary compatibility or data
  migration. No existing Zealor data is opened or changed.
- `confirmed` reflects human review, not proof of truth. The core enforces
  provenance and state, not whether a paraphrase semantically follows a quote.
  Host source-channel classification and review authorization are required.
- Audit APIs retain invalid raw text. Consumers must honor `current_usable` and
  revalidate before use. There is no publication lock after an API returns.
- No physical deletion, backup/restore rollback protection, history import,
  semantic search, full-text/vector index, C2, model, GUI or autonomous behavior.
  Restoring an old copied database is explicitly outside T-02.
- SHA-256 checks detect unmatched changes, not a malicious owner rewriting both
  data and hashes. Python objects/OS access are not hostile-process isolation.
- No new Python minor-version/platform support beyond declared Python 3.12 and
  actual Windows checks is claimed. No skipped key scenarios or mock CI result.

Stop after Draft PR delivery; acceptance belongs to C2.
