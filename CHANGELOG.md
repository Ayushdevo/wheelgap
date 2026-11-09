# Changelog

## Unreleased

- Support `Pipfile.lock` inputs, including default and development dependencies, environment markers, and skipped non-index packages.
- Accept Docker platform names (`linux/amd64`, `linux/arm64`, `linux/arm64/v8`) with `-t`. (#28, thanks [@jwalith4418-Mj](https://github.com/jwalith4418-Mj))
- New `--fail-on missing` (or `fail-on = "missing"` in `[tool.wheelgap]`): accept source builds and only fail when a package can't be installed at all. (#22)
- pre-commit hook: add `id: wheelgap` from this repo to `.pre-commit-config.yaml`. (#23)
- CI now also runs on free-threaded Python 3.14t. (#21)

## 0.2.0 (2026-11-09)

Both features in this release come from [@nodearray](https://github.com/nodearray), wheelgap's first contributor.

- Read default `python`, `targets`, `glibc`, `musl` and `macos` from `[tool.wheelgap]` in `pyproject.toml`. Command-line flags still win. (#5)
- New `--dockerfile PATH`: reads the last `FROM` line of an official `python` image (`python:3.13-alpine`, `--platform=linux/arm64`, `-slim-trixie` …) and uses it for `-p`/`-t`, plus `--glibc` for bookworm/trixie/bullseye and `--musl` for Alpine. Flags still win; other images exit with code 2. (#6)

## 0.1.1 (2026-11-08)

- New `--explain` flag: for each gap, lists the wheels that were rejected and why (wrong libc, glibc/musl/macOS too new, wrong Python or ABI, abi3 on free-threaded), closest misses first. With `--json`, adds a `rejected` list per gap target.
- Regression tests for the Alpine ARM trap: a `manylinux_*_aarch64` wheel never counts for `musl-aarch64`. (Thanks to a suggestion on r/madeinpython.)
- The summary line suggests `--explain` when there are gaps.
- Fixed "1 packages" in the header line.

## 0.1.0 (2026-11-08)

First release.

- Reads `uv.lock`, `pylock.toml` (PEP 751), `poetry.lock`, `requirements.txt` (with `-r` includes), or package names on the command line.
- Targets: `linux-x86_64`, `linux-aarch64`, `musl-x86_64`, `musl-aarch64`, `macos-arm64`, `macos-x86_64`, `win-amd64`, `win-arm64`, for any CPython version including free-threaded builds (`3.14t`).
- Evaluates environment markers and walks the `uv.lock` dependency graph per target, so Windows-only or old-Python-only packages don't show up as false gaps.
- Works offline from lockfiles that record their files; `--online` re-checks against PyPI.
- `--json` output and CI-friendly exit codes (0 clean, 1 gaps, 2 error). Also usable as a GitHub Action.
