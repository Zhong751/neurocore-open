# M1 Python contract: `neurocore.memory/1`

Python 3.12, no runtime dependencies, no model or API credential. Import
`MemoryStore`, `MemoryReader`, `MemoryError`, `ConflictError` from
`neurocore.memory`. Package version remains the T-01 foundation version
`0.0.0.dev0`; the new API and database schema have independent version 1.

## Ownership and lifecycle

`MemoryStore.create(directory, brain_id=...)` explicitly creates
`directory/memory.sqlite3` and a random `store_id`. An existing file is never
overwritten. `MemoryStore(directory, brain_id=...)` opens an existing writer;
`MemoryReader(directory, brain_id=...)` opens it strictly read-only. Missing,
unbound, wrong-brain, unsupported-version or corrupt storage fails. The API does
not invent a Brain identity, discover directories or migrate old instances.

The host supplies its stable `brain_id`. Different directories receive different
`store_id` values even with the same brain label. References bind both IDs.
Copying/restoring databases is outside this contract, not an instance-isolation
or old-backup revocation solution. Source code updates do not touch data.

Only a trusted host should receive `MemoryStore`. In particular, it must determine
speaker/role/provenance from the actual input channel and invoke review only on
an authorized human review action. These are Python library APIs, not an
authentication service or a sandbox against code running as the database owner.
No model, tool or untrusted serialized instruction is allowed to call review.

## Writes

All writers use one SQLite transaction (`BEGIN IMMEDIATE`, foreign keys, FULL
synchronization). The default rollback journal avoids a WAL/cache dependency.
An explicit writer open permits SQLite's own crash-journal recovery. A read-only
open never performs recovery writes; a hot journal requiring writes reports a
database error until the host explicitly opens the writer. No schema migration
or data repair is attempted. Failed initialization leaves the file for explicit
diagnosis, rather than silently overwriting it or creating another identity.

| Method | Required input and result |
| --- | --- |
| `append_event(**fields)` | `event_id`, `source_id`, `source_type`, `speaker_id`, `role`, `provenance`, `conversation_id`, `content`, timezone-aware ISO `occurred_at`; optional JSON `metadata`. Returns `receipt['event']`. |
| `propose_fact(**candidate)` | `conversation_id`, `subject_id`, `predicate`, `value`, `evidence`; optional `basis`, `parents`, `valid_time_text`, `conditions`. Returns pending `receipt['fact']`. |
| `confirm_fact(fact_id, expected_revision=..., reason=...)` | Explicit acceptance, with source/parent revalidation inside the transaction. |
| `review_fact(fact_id, expected_revision=..., action=..., reason=...)` | `accept`, `reject`, `retract`; retains review history. |
| `correct_fact(fact_id, expected_revision=..., reason=..., **replacement)` | Complete new candidate and sources; old revision becomes corrected, descendants withdrawn, new revision pending. Separate confirmation is required. |
| `withdraw_fact(fact_id, expected_revision=..., reason=...)` | Withdraws fact and transitive descendants. Repeat at the old or withdrawn revision has no additional effect. |
| `withdraw_event(event_id, reason=..., expected_version=None)` | Increments source version once, withdraws every dependent fact and its descendants. Repeats preserve epoch/audit and original reason. |

Roles: `user`, `assistant`, `system`, `tool`, `unknown`. Provenance categories:
`user_statement`, `ai_generated`, `ai_suggestion`, `external_unverified`,
`unverified_transcript`, `execution_result`. A category label alone cannot make
an assistant/tool event eligible: user-fact support requires both user role and
user-statement provenance. All original content remains immutable.

Candidate bases: `direct_statement` (default), `reported_statement`,
`model_inference`. Each needs 1–8 exact source spans, including at least one
`supports` relation. Up to eight exact usable parent fact references are allowed.
`context`/`opposes` evidence does not establish user authority. Direct statements
retain the actual user speaker; all spans match the candidate conversation.
The subject must already be a source identity in that conversation.

Every proposal is pending. Accepted direct/reported statements become confirmed.
Accepted model inferences remain pending and unusable as facts/parents, while
`review_status=accepted` records the old M1 “reviewed hypothesis” semantics.
Historical superseded revisions have `status=corrected`; invalidated or retracted
revisions have `status=withdrawn`. Exact predicate conflicts retain review state
but set `conflicted=1`, are not usable and invalidate descendants. This is not
semantic contradiction detection. Rejected/withdrawn exact candidates cannot be
silently reproposed. Original source text is not changed by fact correction.

Event IDs are idempotent when **all fields, including timestamp, match**; retries
must preserve that timestamp. A changed payload under the same ID raises
`ConflictError`. Repeating an exact active proposal reuses the same fact.
Confirmation/correction use compare-and-swap revisions, not universal operation
IDs: a retry after successful confirmation can return `ConflictError`; use
`get_fact` to inspect the durable revision instead of assuming failure rolled
back a previously acknowledged operation. Event/fact withdrawal is idempotent.

## Read-only APIs

| Method | Result |
| --- | --- |
| `authority()` | Contract/schema versions, brain/store IDs and epoch. |
| `get_event(id)` | Audit event, original payload, current status/version/ref and `current_usable`. |
| `cite(event_id, start, end, relation='supports')` | `{ref, start, end, quote, relation}`. Unicode character offsets, not bytes; source must be active. |
| `get_fact(id, revision=None)` | Audit fact (including invalid/history), payload/evidence/parents, ref and explicit `current_usable` plus failure reason. |
| `get_sources(id, revision=None)` | Each original event's source/speaker/time/content, quoted range, version and current reference validity; overall fact usability. |
| `list_valid_facts(subject_id=None, conversation_id=None, limit=100)` | Only usable current facts; full source/ancestor validation. Maximum limit 1000; insertion order, no semantic ranking. |
| `validate_references(refs, expected_epoch=None)` | Overall `valid` and per-reference `valid/reason`; malformed, foreign, stale and invalid records cannot be used. Optional epoch mismatch raises `ConflictError`. |
| `read_connection()` | Restricted read snapshot for diagnostics, with URI `mode=ro`, `query_only`, SQL authorizer; no initialization, DDL/DML, ATTACH or PRAGMA. |

A reference is exactly `{brain_id, store_id, kind, record_id, version, digest}`;
`kind` is `event` or `fact`, `version` is an integer. Event digest binds its
original content and metadata; fact digest binds candidate payload including all
evidence and parent references. Current validity also depends on head revision,
status, review, conflicts, exact spans and the entire parent graph. A stored row
or matching digest alone is insufficient. Read errors fail closed, not as an
empty successful fact response. Standard `sqlite3.Error` is propagated for
storage failures; `MemoryError` represents contract/source/schema errors.

Receipts include `contract_version`, `schema_version`, `brain_id`, `store_id`,
`epoch`, plus the method-specific fields. Every committed mutation advances epoch;
no-op retries and queries do not. Reads use one snapshot then check epoch on a
fresh read; an intervening commit raises `ConflictError`. This is a point-in-time
result, not an everlasting publication lock. Future consumers must revalidate
references/epoch before use; T-02 implements no Composer/model publication.

Audit reads deliberately return withdrawn text for local review. Consumers must
use `current_usable`, `list_valid_facts` and `validate_references`, never treat
an audit payload as active evidence. No raw history import, backup, physical
deletion, UI, model, C2 state or automatic confirmation is included.

## Minimal synthetic example

Install the package with `uv sync --locked`. Then run:

```powershell
uv run --no-sync python -I examples/m1_lifecycle.py
```

The example uses a disposable directory and synthetic text, confirms a sourced
fact, reopens the instance, validates a reference, withdraws the source, and
checks that no valid fact survives. For a real application, supply an explicit
user-selected instance directory and host-owned brain identity; never replace an
existing directory on startup.
