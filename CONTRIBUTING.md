# Contributing to synlynk

Thank you for your interest in contributing.

## Reporting issues

Use the GitHub issue tracker. Select the appropriate template (bug report or feature request) and fill it out completely.

## Development setup

```bash
git clone https://github.com/nikhilsoman/synlynk.git
cd synlynk
# No dependencies — Python 3.8+ stdlib only
```

Run tests:

```bash
pytest tests/
```

Run the CLI directly:

```bash
python3 bin/synlynk.py --version
```

## Branch naming

```
feat/<short-description>    # new features
fix/<short-description>     # bug fixes
chore/<short-description>   # tooling, docs, CI
```

## Commit style

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add watch daemon with file polling
fix: check_flatline now writes to sentinel.md
docs: update README install instructions
test: add conftest project_dir fixture
chore: add GitHub Actions CI workflow
```

## Pull requests

- One logical change per PR
- All tests must pass (`pytest tests/`)
- Update `CHANGELOG.md` under `[Unreleased]`
- Fill out the PR template

## Code conventions

- Single-file architecture: all logic lives in `bin/synlynk.py`
- stdlib only — no external dependencies
- Python 3.8+ compatible
- No inline comments unless the reasoning is non-obvious
- Tests use pytest with `tmp_path` and `monkeypatch.chdir` for filesystem isolation

## Releasing

Releases are made by the maintainer. Version bumps follow [Semantic Versioning](https://semver.org/).
