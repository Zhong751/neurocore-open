# Sensitive-file gate

Run `python scripts/check_sensitive.py` from the repository root. The command is
read-only and requires Python 3.12+ and Git. It has no Python package dependencies.
Use `--repo PATH` to check a different Git working tree. Exit codes are `0` for a
clean index, `1` for findings, and `2` when the Git index cannot be inspected.
Diagnostics include only the escaped path and rule name; matching values and Git
error output are never printed.

The input is **every entry in the current Git index**, not just changed files and
not the working-tree version. Stage intended changes before running the gate.
An unstaged cleanup does not hide a secret still staged for a commit. `.gitignore`
is a convenience; force-added files still pass through this gate. Run the gate
again after any change to staged content.

## Rules

- Denied directories cover credential stores, local user instances and data,
  databases, logs, caches, virtual environments, builds, backups, generated output,
  and chat exports. Denied filenames cover `.env` variants (including templates),
  credential files, database files and sidecars, logs, backups, and common chat
  export names. Path matching is case-insensitive and applies at any depth.
- Media, SVG, model, archive, and binary document filenames are denied. No character
  assets or other binary files are approved in this initial repository. Ordinary
  source code, Markdown documentation, configuration, and lockfiles are allowed.
- Content patterns detect private-key headers, AWS access-key IDs, common GitHub,
  Slack, Google, service/Stripe key formats, JWT-shaped strings, and passwords in
  URLs. A separate rule detects assignments to common credential names, including
  prefixed names such as provider API keys, in common code/configuration syntax.
- Empty strings and a small explicit set of documentation placeholders are
  allowed, as are uppercase angle-bracket placeholders and recognized environment
  references. The exact patterns and allowlist live in
  `scripts/check_sensitive.py`. Known key-format rules still apply to placeholders.
- Non-UTF-8 blobs, NUL/control-containing blobs, files over 4 MiB, unreadable blobs,
  symlinks, submodules, and unmerged index entries fail closed. Executable UTF-8
  scripts are allowed. A Git error cannot be reported as a clean result.

Temporary directories, local verification output, wheel test environments, and
local/generated asset directories are excluded as well. The Python source path
`src/neurocore/models/` remains allowed; model artifact extensions are denied.

The scanner deliberately does not classify arbitrary high-entropy text as a
secret. Normal package integrity hashes in `uv.lock` remain valid inputs.

## Limits and maintenance

This is a small deterministic review gate, not proof that a repository has no
private information. Novel credential formats, obfuscated/encoded values,
multiline or computed assignments, and ordinary personal text may evade these
patterns. The assignment rule is lexical, not a language parser: unusual variable
expressions or type annotations can require review. A UTF-8 text asset with no
denied name or matching content can pass. Do not approve it solely on that basis.

The command checks the current index only: it does not scan history, remote refs,
untracked files, ignored files, or files staged concurrently after enumeration.
It does not contact any provider or test whether a credential works. Run it in a
stable checkout; history review is separate work. Git's own repository ownership
checks remain in effect.

An intentional public example should use an explicit placeholder or runtime
environment lookup. Before allowing a new file class, review why it belongs in
the public repository, then update the scanner, `.gitignore`, tests, and this
document together. Do not bypass the gate with `git add -f`.

Run the focused checks with:

```console
python -m unittest discover -s tests -p "test_sensitive.py" -v
python -m unittest discover -s tests -p "test_gitignore.py" -v
```

The tests create independent temporary Git repositories. Credential-shaped test
values are assembled at runtime from synthetic fragments; no working credentials
or complete credential-shaped fixtures are stored in the repository.
