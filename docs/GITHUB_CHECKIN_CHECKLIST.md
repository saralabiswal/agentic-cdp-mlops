# GitHub Check-In Checklist

Use this checklist before the first GitHub push.

## Recommended Repository Name

```text
enterprise-ai-decision-intelligence
```

## Files Intended For Git

Commit source code, configuration, tests, UI assets, and documentation:

```text
README.md
Makefile
.github/
architecture/
data/
deploy/
docs/
infra/
models/
pipelines/
scripts/
stack/
tests/
ui/
use_cases/
requirements.txt
requirements-ml.txt
pytest.ini
```

## Files Intentionally Ignored

Runtime and local-only files are excluded by `.gitignore`:

```text
.venv/
.venv*/
__pycache__/
.pytest_cache/
artifacts/
artifacts_*/
.env
*.log
node_modules/
```

## Pre-Push Validation

Run:

```bash
python3 -m pytest -q
python3 docs/generate_tech_docs.py --check
python3 docs/generate_api_contracts.py --check
python3 docs/generate_user_guide_pdf.py
```

Optional standalone validation:

```bash
make smoke-standalone
```

## First Commit Commands

```bash
git init
git add .
git status
git commit -m "Initial enterprise AI decision intelligence app"
git branch -M main
git remote add origin <github-repo-url>
git push -u origin main
```

## Notes

1. Choose and add a project license before making the repository public.
2. Do not commit `artifacts/`; the app can regenerate runtime artifacts locally.
3. UI-facing artifact paths are normalized to repo-relative `artifacts/...` strings for portability.
