# Contributing to Portal

Thanks for helping improve Portal.

## Development Setup

```bash
git clone https://github.com/ckindle-42/portal
cd portal
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[all,dev]"
```

## Running Tests

```bash
# Unit tests (fast, no services required)
pytest tests/unit/ -v

# Integration tests (mocked services, no Ollama required)
pytest tests/integration/ -v

# All tests with coverage
pytest --cov=portal --cov-report=term-missing
```

## Code Quality

```bash
# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/

# Type check
mypy src/portal --ignore-missing-imports
```

The CI pipeline (`ci.yml`) runs all three on every push and PR.

## Reproducible Builds

For a fully reproducible install (pinned transitive deps), use `pip-compile`:

```bash
pip install pip-tools
pip-compile pyproject.toml --output-file requirements.lock
pip install -r requirements.lock
```

Commit `requirements.lock` if reproducibility across machines matters for your deployment.

## Commit Style

| Prefix | When to use |
|--------|-------------|
| `fix:` | Bug fix |
| `feat:` | New feature |
| `chore:` | Maintenance (deps, CI, docs) |
| `refactor:` | Refactor with no behaviour change |
| `test:` | Test additions / fixes |

Example: `fix: switch OllamaBackend to /api/chat for tool call support`

## Branching

- `main` / `master` — stable, tagged releases only
- Feature branches — `<prefix>/<short-description>-<id>`
- CI runs automatically on all `claude/**` branches and PRs to `main`

## Release Process

1. Bump `version` in `pyproject.toml` and `__version__` in `src/portal/__init__.py`
2. Add a `## [x.y.z] - YYYY-MM-DD` section in `CHANGELOG.md`
3. Commit: `chore: release vx.y.z`
4. Tag: `git tag vx.y.z && git push origin vx.y.z`
5. The `release.yml` workflow creates the GitHub Release automatically

## Architecture Overview

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Filing Issues

Please include:
- Portal version (`curl http://localhost:8081/health | jq .version`)
- Hardware profile (M4 Mac / Linux CUDA / WSL2)
- Relevant log output (`bash hardware/m4-mac/launch.sh logs portal`)
