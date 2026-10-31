# NeuroCore public repository

- This repository has an independent public Git history. Never copy private
  repository history, credentials, user instances, conversations or character art.
- T-01 is infrastructure only. Do not implement cognition, memory, chat, agents,
  desktop behavior, computer control or migrations as part of this task.
- Work on a branch based on public `main` and submit a draft PR. C2 independently
  reviews it; do not merge or publish a release without explicit authorization.
- Keep runtime dependencies empty for T-01. Review source and license before
  adding dependencies or Actions; pin Actions to full commit SHAs.
- Use Python 3.12 and the exact uv version in `pyproject.toml`. Run locked sync,
  import checks, unittest, build and `scripts/check_sensitive.py` before pushing.
- Scan staged content before publication, including force-added files. Never
  put real credentials into tests; assemble clearly synthetic fixtures at runtime.
- Preserve failure evidence in the delivery report. YAML validation is not proof
  of a successful Windows runner execution. Report skips and unverified items.
- A secret scanner is a limited pattern/path check, not a privacy proof. Review
  every public diff for personal data and unapproved assets.
