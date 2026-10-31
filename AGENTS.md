# NeuroCore public repository

- This repository has an independent public Git history. Never copy private
  repository history, credentials, user instances, conversations or character art.
- T-01 and T-02 are accepted. T-03 adds character seeds, independent instance
  creation and strictly read-only doctor checks to public main `7a544c5`.
  Do not add cognition, models, chat, agents, desktop behavior, computer control,
  private-instance migration, full backup restore or physical deletion.
- Work on a branch based on public `main` and submit a draft PR. C2 independently
  reviews it; do not merge or publish a release without explicit authorization.
- Keep runtime dependencies empty for T-03. Review source and license before
  adding dependencies or Actions; pin Actions to full commit SHAs.
- Use Python 3.12 and the exact uv version in `pyproject.toml`. Run locked sync,
  import checks, unittest, build and `scripts/check_sensitive.py` before pushing.
- Scan staged content before publication, including force-added files. Never
  put real credentials into tests; assemble clearly synthetic fixtures at runtime.
- Preserve failure evidence in the delivery report. YAML validation is not proof
  of a successful Windows runner execution. Report skips and unverified items.
- A secret scanner is a limited pattern/path check, not a privacy proof. Review
  every public diff for personal data and unapproved assets.
- M1 source read/policy provenance is limited to `docs/T02_sources.md`. Explicit
  writers own review; raw/model input cannot self-confirm facts. Read-only APIs
  must not initialize storage. Existing stores never silently become new Brains.
- Seeds and example dialogues are initial guidance, never M1 events or user
  facts. Use synthetic fixtures only; do not publish a formal Zealor voice/art.
- Instance creation reserves a new directory and publishes its manifest last.
  Never overwrite existing targets or silently delete failed creation data.
  Doctor only reads bounded file snapshots; no source SQLite open, repair,
  recovery, cursor advance or model connectivity checks.
