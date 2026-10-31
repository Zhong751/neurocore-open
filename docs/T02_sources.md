# T-02 source boundary and policy provenance

This task reads only named M1 source/test files from the earlier private
NeuroCore implementation at `11a38571193a3278aaa839b9762561dcf3c5546a`.
It does not import that repository's history, data, configuration or fixtures.

| Read allowlist | Responsibility / dependencies | Decision |
| --- | --- | --- |
| `AGENTS.md` | Prior project authority rules | Instructions only |
| `vendor/m1/pyproject.toml` | Dependency metadata | Do not import dependencies |
| `vendor/m1/src/zealor/database.py` | SQLite schema / layout / WAL prerequisite | Inspect schema prefix only; independent new schema |
| `vendor/m1/src/zealor/memory_contracts.py` | Pydantic candidates and exact spans | Preserve constraints using standard Python |
| `vendor/m1/src/zealor/memory.py` | Review, revision, conflict, suppression, dependency invalidation; depends on layout, search, tokenizer | Reimplement bounded policy; no whole-file copy |
| `vendor/m1/src/zealor/ai_schema.py` | Source eligibility by role and provenance | Preserve eligibility semantics for supported new events |
| `vendor/m1/src/zealor/live.py` | Event identity, idempotency, correction | Preserve design; omit import/archive/model machinery |
| `vendor/m1/src/zealor/readonly_reader.py` | URI read-only, query-only, SQL authorizer, reference validation | Preserve independent read boundary |
| `neurocore/memory_service.py` | Reference and epoch recheck | Design reference only; exclude optional external index |
| `vendor/m1/tests/test_memory.py` | Review/correction/conflict counterexamples | Re-express selected assertions with fresh runtime synthetic data |
| `vendor/m1/tests/test_ai_evidence_guards.py` | AI-source exclusion, reviewed inference remains ineligible | Preserve policy counterexamples |
| `tests/test_readonly_reader.py` | Read-only and stale references | Re-express for public schema |

Initially considered but **not read or migrated**: `neurocore/source_events.py`
and `tests/test_source_events.py`. The M1 files above suffice. No C2, models,
desktop, control, private Brain, backup, log or business-data fixture is read.

## Provenance and license decision

The private M1 package declares no standalone license and its tracked tree has
no M1 LICENSE/NOTICE. This is not treated as permission to copy unspecified
third-party code. No private source file, executable code block, test fixture or
third-party implementation is copied verbatim into this public package. T-02
implements the authorized project's reviewed policies independently, under this
public repository's existing Apache-2.0 license. Unknown-origin components are
excluded, rather than relicensed. No private Git parent/object is imported.

Inspection fingerprints (SHA-256, for C2's private-side comparison):

| File basename | Digest |
| --- | --- |
| `memory.py` | `8c8c8c234596522c52c1e703ca897ba1521f0e261683636663806e61ffc1d7ac` |
| `memory_contracts.py` | `6405be0be1ef05291da922c3169cb11d4beb052972eaa27e350a3aa2511e8bc2` |
| `ai_schema.py` | `e7d963d6b6c6e74b484bdc67add29a1cd5af552843106af82fa67a2a55ef7e61` |
| `live.py` | `ff1ea4506a60e0162cf700f964ac4a6795d7ba9374e6d8c32118c94bd11cb444` |
| `readonly_reader.py` | `b355ad3d0479f3d46159316e058b972eeb22c261076b3ee663d5c056e96f7b08` |

No new runtime, test or build dependency is added. SQLite is provided by
Python's `sqlite3`; no SQLite executable is vendored. Existing Python/tool/Action
licenses and pins remain in [dependencies.md](dependencies.md).

## Policy mapping

- Every proposal starts pending, requires exact supporting source spans, and
  binds direct statements to the actual speaker and conversation.
- Only user-role, user-statement evidence supports direct/reported facts.
  Other provenance may support an explicitly labelled model inference or provide
  contextual/opposing evidence for a reported statement, never user authority.
- Explicit acceptance of a model inference records `review_status=accepted`
  but leaves public `status=pending`, `current_usable=false`. This maps the old
  accepted-but-ineligible inference; it does not convert it into a user fact.
- Dependencies require currently usable, explicitly accepted parent revisions.
  Any necessary source, parent version or conflict invalidates descendants.
- Corrections retain original records and create a new pending revision; they
  never auto-confirm replacement text. Exact predicate conflicts remain excluded
  until explicit human resolution. Rejected/withdrawn proposals are suppressed.

Not migrated: file imports and archive format, FTS/tokenizer, model extraction,
learning episodes, backup restore, source-scope import controls, C2 publication
or OS permissions. New public instances are a distinct schema; this is not a
private Brain migration tool.
