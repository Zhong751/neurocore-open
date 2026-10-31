# T-01 tools, sources and licenses

Reviewed on 2026-10-31. The installed `neurocore` package has **no runtime
dependencies**. Tests and the sensitive-file checker use Python's standard
library. No private implementation or third-party application source was copied.

| Component | Exact selection | Purpose and license |
| --- | --- | --- |
| Python | Supported `>=3.12,<3.13`; local verification 3.12.16 | Interpreter and `unittest`; [Python license](https://docs.python.org/3.12/license.html), including upstream notices |
| uv | `0.13.6`, release commit `329bf9448afd9f9088d14a4d57fbc61eb454f117` | Environment, lock and build tool; [MIT OR Apache-2.0 metadata](https://github.com/astral-sh/uv/blob/0.13.6/Cargo.toml), [MIT](https://github.com/astral-sh/uv/blob/0.13.6/LICENSE-MIT), [Apache-2.0](https://github.com/astral-sh/uv/blob/0.13.6/LICENSE-APACHE) |
| uv_build | `0.13.6` | Pure-Python build backend; [versioned PyPI metadata](https://pypi.org/project/uv-build/0.13.6/), MIT OR Apache-2.0 |
| actions/checkout | `3d3c42e5aac5ba805825da76410c181273ba90b1` (`v7.0.1`) | Checkout; [fixed LICENSE](https://github.com/actions/checkout/blob/3d3c42e5aac5ba805825da76410c181273ba90b1/LICENSE), MIT |
| astral-sh/setup-uv | `68559e99cc807c1eb7e9238fd43a15bba460eec2` (`v10.3.3`) | Install pinned uv; [fixed LICENSE](https://github.com/astral-sh/setup-uv/blob/68559e99cc807c1eb7e9238fd43a15bba460eec2/LICENSE), MIT |

Matching uv/uv_build versions use uv's bundled build backend. The backend is
exactly pinned in `pyproject.toml`; it is not a runtime dependency in `uv.lock`.
The lock contains only the local editable package because there are no runtime
or test packages to resolve. Python patch versions may change within the declared
3.12 support range; that is separate from dependency lock consistency.

## Source review and supply chain boundaries

- Reviewed the official uv [project](https://docs.astral.sh/uv/guides/projects/),
  [build backend](https://docs.astral.sh/uv/concepts/build-backend/) and
  [GitHub integration](https://docs.astral.sh/uv/guides/integration/github/)
  documentation. No large framework is necessary for T-01.
- Reviewed checkout's fixed `action.yml` and README: Node 24, shallow checkout,
  submodules/LFS off by default, and credentials persisted by default. This
  workflow explicitly disables credential persistence.
- Reviewed setup-uv's fixed `action.yml`, `src/setup-uv.ts`, and download source:
  it downloads a selected release, validates its checksum before extraction, and
  can restore/save caches. T-01 fixes the version and disables both caches and
  cache saving. This is a focused source review, not an audit of every bundled
  JavaScript dependency.
- Workflow permissions are `contents: read`. It uses ordinary `pull_request`,
  `push` on `main`, and manual dispatch; no `pull_request_target`, secret input,
  write permission, package upload or release action is used. See
  [GitHub's secure-use reference](https://docs.github.com/en/actions/reference/security/secure-use).
- Git is used as an existing developer/runner tool and is not bundled in Python
  distributions; [Git's license](https://github.com/git/git/blob/master/COPYING)
  is GPL-2.0. uv-managed Python comes from
  [python-build-standalone](https://github.com/astral-sh/python-build-standalone);
  upstream interpreter and bundled component notices remain applicable. No
  interpreter, Git executable, uv binary or Action code is vendored here.

For local verification, the Windows uv wheel was downloaded from official PyPI
metadata and checked before extracting `uv.exe`:

- Wheel: `uv-0.13.6-py3-none-win_amd64.whl`
- SHA256: `7c9bc35ccb65932d8dc10a0669f9c805eaa3c9827ce18ecbecb1bd67944b2cdf`
- Extracted executable SHA256: `81ea623608f8c17720c62efd0a380a8ead380c4d365ba6968e9d279a2319c674`

`LICENSE` is the unmodified complete text downloaded from
[Apache's official source](https://www.apache.org/licenses/LICENSE-2.0.txt):
11,358 bytes; SHA256
`cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`.
No character art, media, models or private fixtures are included.
