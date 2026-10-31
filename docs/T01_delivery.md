# T-01 delivery record

Status: R-01-F01 confirmed the original F-01 diagnostic leak fix, but identified
F-02 filename boundary misses. T-01 remains pending independent acceptance.
This second scoped repair awaits C2 retest. Do not merge or start T-02. If C2
returns NO-GO again, stop and request a user decision on the scanner approach;
do not autonomously submit a third patch round.

## T-01-F02: filename credential boundaries

Fixed failing baseline: `e40535e4e08a0d0a78e5c872ab36ee094af9d7a5`.
The path check reused prose patterns containing Unicode `\b`. Underscores,
ASCII letters and Chinese characters are word characters, so an intact token
next to them could lose the required boundary. Baseline reproduction confirmed
the misses while token echo count remained zero: F-01 redaction did not regress.

`PATH_RULES` now derives a separate pattern from each existing content pattern
by removing only an explicit leading/trailing `\b`. It preserves core character
classes, length thresholds, regex flags and any internal boundaries; it does not
globally replace boundaries or modify `CONTENT_RULES`. `path_violations` unions
these matches with the previous checks and preserves failures for invalid or
oversized data. No surrounding filename character can block a match of a
complete current credential core. All path components retain their original case.

One dynamically generated, unchanged GitHub-shaped value was used across the
matrix below. Each test confirms the complete expected Git-index path set and
reads each indexed blob to verify its harmless body. The scan must return 1 and
report `path-github-token` for every index-entry number, without echoing the value
or any raw path. No raw token-bearing result or complete fixed fixture is saved.

| Filename template | Baseline detects | Repaired result |
| --- | --- | --- |
| `<Token>.txt` | Yes | Rejected |
| `config-<Token>.txt` | Yes | Rejected |
| `config.<Token>.txt` | Yes | Rejected |
| `config <Token>.txt` | Yes | Rejected |
| `config_<Token>.txt` | No | Rejected |
| `说明<Token>.txt` | No | Rejected |
| `说明_<Token>.txt` | No | Rejected |
| `<Token>_backup.txt` | No | Rejected |
| `<Token>说明.txt` | No | Rejected |
| `config<Token>.txt` | No | Rejected |
| `<Token>backup.txt` | Yes | Rejected |
| `说明_<Token>说明.txt` | No | Rejected |
| `目录_<Token>/notes.txt` | No | Rejected |

Additional actual coverage:

- Mixed-case GitHub payloads remain valid shapes; uppercase GitHub prefixes,
  lowercase AWS prefixes/payloads and altered Google prefixes do not match rules
  that were case-sensitive. Findings equal the expected subset, not merely a
  global nonzero result.
- Six normal/incomplete filenames pass, including an explicitly too-short
  credential payload. Body-only and body-plus-embedded-name secrets still fail.
- The original body boundary behavior is asserted independently. AST comparison
  also confirms eleven original definitions, including content rules, body
  checking, Git reading, CLI errors and diagnostic output, are unchanged.
- All F-01 error/redaction tests remain. An extra in-memory intentionally failing
  index assertion verifies the new fixture check cannot print its dynamic value.

Local Windows / Python 3.12.16 / uv 0.13.6: `uv sync --locked`, `uv lock --check`,
the full test suite (**36 passed, zero skipped, 20.464s**) and `uv build` passed.
All original 29 test methods are retained; seven F-02 methods were added. The
exact repair SHA and actual Windows CI run are recorded in the existing
[Draft PR #1](https://github.com/Zhong751/neurocore-open/pull/1) delivery description;
older CI runs below do not establish F-02 acceptance.

Only the scanner, its tests, this report and `docs/security_checks.md` change.
No dependency, project structure, workflow permission, license, private project
or Zealor data is changed. File-number diagnostics and Git-index scope remain.
No false positive appeared in the six normal/incomplete cases. Deliberately
broader substring matching can reject an otherwise legitimate longer filename
that contains a complete credential shape; this is the filename policy, not
credential validation. Unknown, encoded/split credentials, ordinary personal
text and history outside the index remain outside reliable detection. Body
semantics retain their existing limits by design.

## T-01-F01: secret-bearing filenames in diagnostics (historical)

Reviewed baseline: `45bcc2077ba7956670518a394df5508ffe0c63d5`. The baseline printed
`json.dumps(path)` for every finding. JSON escapes control characters but leaves
credential text intact; one filename triggered three findings and leaked the
same dynamic synthetic value three times. The content rules were also applied
only to blobs, so a credential-shaped filename with a harmless body passed.

The fix retains only integer index-entry numbers and fixed categories in
findings. It applies the unchanged content rules to original-case path bytes,
and replaces argparse's value-bearing diagnostics with a fixed category and
program label. It does not redact by quoting or masking only the body. Test
assertions and fixture failures no longer include raw outputs, paths or values.

Only five existing files change: `scripts/check_sensitive.py`,
`tests/test_sensitive.py`, `README.md`, `docs/security_checks.md` and this report.
The package, dependency lock, CI permissions/workflow, `.gitignore` and license
are unchanged. AST comparison against the reviewed commit confirmed the original
rule constants, placeholder logic, blob checker and Git helper are unchanged.
The Git-index scan scope and exit codes remain unchanged.

| Counterexample | Before | After / regression coverage |
| --- | --- | --- |
| F01-A: same dynamic token in filename and body | Exit 1; stdout 0, stderr 3 complete token occurrences | Exit 1; stdout 0, stderr 0; file number plus four fixed findings, including path detection |
| F01-B: token only in filename | Exit 0, not detected | Exit 1, no token echo; GitHub-shaped and case-sensitive AWS/Google-shaped dynamic cases |
| F01-C: ordinary filename and content | Passed | Existing clean-source/docs/lock test still passes; all original 23 test cases retained |
| F01-D: index/blob/CLI error | Path/argument diagnostics could carry values | Missing blob under a sensitive filename, injected index exception and unknown CLI argument all fail without value echo |
| F01-E: failing test output | Assertions could render secret operands or raw stderr | Six inner failures covering status/category/redaction assertions and Git/file setup errors captured in memory; reports contain no fixture value |

Local Windows, Python 3.12.16 / uv 0.13.6: `uv sync --locked`, `uv lock --check`,
the full `unittest discover` run (**29 passed, zero skipped, 15.441s**) and
`uv build` passed. The 29 tests are the original 23 plus six new F-01 test methods;
F01-C reuses the retained normal-file coverage. Before/after probes published
only exit codes and occurrence counts; raw token-bearing output was never saved.
Disposable repositories are removed after tests.

The new commit must run the existing Windows workflow; the exact remediation SHA
and actual run link are recorded in the existing [Draft PR #1](https://github.com/Zhong751/neurocore-open/pull/1)
delivery description. The old 23-test CI links below are historical evidence,
not acceptance evidence for F-01. C2 must retest F-01 and determine whether prior
acceptance results still apply.

The scanner remains lexical and index-only: novel/encoded credential forms and
ordinary personal text may escape detection. This change prevents diagnostics
from exposing raw paths regardless of whether a path matches a known pattern;
it does not claim broader privacy detection or full-history scanning.

## Original T-01 repository and scope

- Public repository: <https://github.com/Zhong751/neurocore-open>
- Draft PR: <https://github.com/Zhong751/neurocore-open/pull/1>
- Base: public `main`; root commit `ecc0e157c37a04fbfd030e934c9724e14e291ac5`
  contains only an initialization README.
- Development branch: `codex/t01-foundation`.
- Validated implementation commit: `4423e9d585d1e119329e2ba88d2c43c5e67a29ea`.
  The follow-up delivery-record commit changes documentation only; its exact
  head and associated checks are available in PR #1 and the final delivery message.
- Initialized with `git init`, not a clone/fork/worktree of a private repository.
  No private commits, branches, tags, source, instance or character data imported.
- Package: `neurocore`, version `0.0.0.dev0`, Apache-2.0, Python 3.12 only.
- Structure uses `src/neurocore/` instead of root `neurocore/` to verify installed
  imports without relying on the checkout directory. Empty subsystem modules have
  docstrings only. WPF, characters and evals are text-only boundaries.
- No chat, cognition, memory, persona, goals, desktop behavior, model calls,
  computer control, migrations, releases or runtime frameworks were implemented.

## Validation commands

```powershell
uv sync --locked
uv lock --check
uv run --no-sync python -I -c "import neurocore; import neurocore.core, neurocore.perception, neurocore.models, neurocore.api"
uv run --no-sync python -m unittest discover -s tests -v
uv run --no-sync python scripts/check_sensitive.py
uv build
```

The workflow also installs the built wheel without dependencies into a second
environment and imports it with Python isolated mode. The scanner is run against
all staged files before pushing; only text source/config/docs and the dependency
lock may be published. Synthetic scanner fixtures live in temporary independent
Git repositories and are not committed as complete credential-shaped strings.

## Original T-01 execution results (superseded acceptance conclusion)

Local Windows, uv 0.13.6, CPython 3.12.16:

| Check | Actual result |
| --- | --- |
| `uv sync --locked` and `uv lock --check` | Passed; only local `neurocore` installed |
| Isolated installed imports | All five modules imported |
| `unittest discover` | Final local run: 23 tests passed, zero skips, 13.614 seconds |
| Git-index sensitive check | All 25 tracked/staged text files passed |
| Build | Wheel and source distribution built |
| Clean wheel installation | Installed without dependencies; isolated imports and bundled canonical Apache-2.0 license passed |

Actual GitHub-hosted Windows verification:

- [Run 41188113809](https://github.com/Zhong751/neurocore-open/actions/runs/41188113809)
  on the implementation commit above: **success**, event `pull_request`.
- [Job 124499085302](https://github.com/Zhong751/neurocore-open/actions/runs/41188113809/job/124499085302):
  runner label `windows-2025`; logs confirm **Microsoft Windows Server 2025**,
  CPython **3.12.10**, and **23 tests in 9.933s, OK**, no skipped tests.
- Locked installation, lock consistency, imports, synthetic checks, whole-index
  scan, sdist/wheel build, separate wheel install and bundled-license check all
  completed successfully. The job logs were inspected, not just workflow YAML.
- Local 3.12.16 and runner 3.12.10 are both inside the declared 3.12 support range.
  No other Python minor version or non-Windows runner is claimed as accepted.

An unauthenticated request to public `main/README.md` returned HTTP 200. The
implementation history had exactly two reachable commits and one independent
root, no tags, no alternate object store and no shared worktree Git directory.
All 26 distinct historical blobs in those two commits also passed content rules;
the normal CI scanner checks the current index, not history. The root initializer
is the only content on `main` until C2 approves and a separate merge is authorized.

## File inventory

25 files: 24 new files plus the expanded initialization `README.md`; total diff against `main` is +1305/-3 lines, with no binary assets:

```text
.gitattributes
.github/workflows/ci.yml
.gitignore
.python-version
AGENTS.md
LICENSE
README.md (modified)
characters/_template/README.md
docs/T01_delivery.md
docs/dependencies.md
docs/security_checks.md
evals/README.md
pyproject.toml
scripts/check_distribution.py
scripts/check_sensitive.py
shell-wpf/README.md
src/neurocore/__init__.py
src/neurocore/api/__init__.py
src/neurocore/core/__init__.py
src/neurocore/models/__init__.py
src/neurocore/perception/__init__.py
tests/test_gitignore.py
tests/test_package.py
tests/test_sensitive.py
uv.lock
```

## Failures and environment recovery

- The default sandbox could not use the system Git credential helper. An
  authorized host-process check succeeded using the existing generic GitHub
  login, verified account `Zhong751` and `repo`/`workflow` scopes, then confirmed
  the target did not exist. No new login or pasted token was required; credentials
  were neither printed nor written into this repository. The connector has no
  repository-creation tool, so creation used GitHub's official API.
- The new directory was owned by the sandbox identity. Host Git initially
  rejected it as dubious ownership. Commands trusted only this exact new path
  with a per-command `safe.directory`; global Git configuration was not changed.
- The first initial push had a TLS handshake failure; retry succeeded with TLS
  verification unchanged. Default-sandbox package download was blocked by the
  network policy; authorized download and checksum verification succeeded.
- A supplementary unauthenticated GitHub release-metadata query hit rate limit
  HTTP 403. Version/Action refs and licenses were verified through official
  versioned sources; no checksum was invented or TLS verification disabled.
- The GitHub connector could read the new repository but returned HTTP 403
  `Resource not accessible by integration` for PR creation. The existing generic
  Git login successfully created the draft through the official API. A transient
  connector transport error during CI status lookup was likewise resolved with
  an authenticated read-only official API query. No new token or expanded scope
  was requested. Web-index cache misses were not treated as visibility evidence;
  anonymous direct HTTP successfully verified public access instead.
- A synthetic test initially used Windows-reserved `nul.txt`; changing the
  fixture to `nul-byte.txt` allowed the intended binary-content check to run.
- Initial packaging assertions assumed metadata preserved whitespace and that
  an editable install contained an archived license file. Actual metadata
  normalizes spacing, and uv's editable install declares `License-File` while
  the built wheel contains the file. Tests now check metadata semantically,
  verify the canonical source license, and independently verify the actual
  wheel's bundled license after installation. Both initial failures are retained
  here; the final 23-test run and wheel check passed.

Those original automated checks had no failures/skips, but R-01 subsequently
identified F-01; they did not cover secret-bearing filename diagnostics.
Earlier environment and test-development failures above remain disclosed. Installing directly from
the sdist was not separately tested; the wheel was built from that sdist and
installed. No public package release was created. Branch-protection rules and a
third-party full-history secret scanning service were not configured by this task.

## Security and review boundaries

See [security checks](security_checks.md) for patterns, path rules, synthetic
tests and limitations; see [dependency review](dependencies.md) for sources and
licenses. Pattern scanning cannot prove the absence of arbitrary personal text
or novel/obfuscated secrets. C2 should inspect the entire small diff, check the
root history, pinned Actions, no-write workflow permissions, index-based scan,
lock behavior and actual Windows runner results.

No old private repository source/history, Brain, private database, model key,
formal artwork or existing development instance was opened or modified for
T-01. Existing tool executables were used before this task's isolated Python
environment was ready. The only authentication used was the generic GitHub
login needed for this explicitly authorized public repository task.
