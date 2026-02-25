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

Portal releases are **source-only**. There are no compiled artefacts or pip
packages to publish — end users run Portal directly from the extracted source
on their own machines. The GitHub Release asset is a plain zip archive of the
versioned source files.

### Automated (recommended)

```bash
# 1. Add a ## [x.y.z] - YYYY-MM-DD section to CHANGELOG.md first, then:
python scripts/release.py x.y.z

# 2. Push the commit and tag; the workflow does the rest
git push origin HEAD && git push origin vx.y.z
```

`scripts/release.py` validates the version bump, verifies the CHANGELOG entry,
updates both version files, and creates the git commit + annotated tag.

### Manual (if needed)

1. Add a `## [x.y.z] - YYYY-MM-DD` section to `CHANGELOG.md`
2. Bump `version` in `pyproject.toml` and `__version__` in `src/portal/__init__.py`
3. Commit: `chore: release vx.y.z`
4. Tag: `git tag -a vx.y.z -m "Portal vx.y.z"`
5. Push: `git push origin HEAD && git push origin vx.y.z`

### What the workflow does

The `release.yml` GitHub Actions workflow triggers on the version tag and:

1. Verifies the tag matches `pyproject.toml`
2. Extracts the release notes from `CHANGELOG.md`
3. Builds `portal-vx.y.z.zip` — a zip archive containing `src/portal/`,
   `hardware/`, `mcp/`, `deploy/`, `pyproject.toml`, `.env.example`,
   `Dockerfile`, `README.md`, `CHANGELOG.md`, and `LICENSE`
4. Creates the GitHub Release with the zip attached

## Architecture Overview

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Filing Issues

Please include:
- Portal version (`curl http://localhost:8081/health | jq .version`)
- Hardware profile (M4 Mac / Linux CUDA / WSL2)
- Relevant log output (`bash hardware/m4-mac/launch.sh logs portal`)
