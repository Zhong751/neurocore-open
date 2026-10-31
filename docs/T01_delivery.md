# T-01 delivery record

Status: T-01 implementation and local/Windows CI checks passed; C2 independent
acceptance pending. Do not merge or start T-02 based on this draft.

## Repository and scope

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

## Results

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

There are no remaining failed/skipped required T-01 checks. Earlier environment
and test-development failures above remain disclosed. Installing directly from
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
