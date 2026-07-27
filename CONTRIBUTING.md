# Contributing to Kulima FLEX

Thank you for your interest in contributing. Kulima FLEX is an investment intelligence platform designed for the African venture ecosystem. Contributions that strengthen its analytical rigor, geographic coverage, code quality, and documentation are welcome.

---

## Development Philosophy

Kulima FLEX is built to operate at partner quality. Contributions should meet that standard.

- **Correctness before cleverness.** The system's outputs influence investment decisions. Prefer safe, legible code over compact but opaque logic.
- **Additive, not destructive.** The core scoring, recommendation, and trust layer pipelines are carefully calibrated. Contributions to these systems require explicit discussion before implementation.
- **Africa-specific knowledge is valued.** If you understand African market dynamics, founder ecosystems, or regulatory environments, that expertise is directly applicable here.
- **Documentation is not optional.** New modules require module-level docstrings and entry in the appropriate `docs/` file.

---

## What We Welcome

- Bug fixes and test coverage for existing modules
- New geographic coverage (market data, sector taxonomies, regulatory insights)
- Documentation improvements — especially worked examples and conceptual explanations
- Performance improvements to the research and analysis pipeline
- New export formats (LP reports, board pack formats)
- Language support for OSINT (French, Swahili, Portuguese, Arabic)
- UI improvements to the Streamlit dashboard

---

## What Requires Discussion First

Before opening a pull request for any of the following, open an issue or start a discussion:

- Changes to `kulima/scoring.py` or any score formula
- Changes to agent prompts in `kulima/agents/`
- Changes to the Evidence Integrity Engine (`kulima/evidence_integrity.py`)
- Changes to the Twin Syndicate archetypes (`kulima/config.py`)
- Changes to data models in `kulima/models.py`
- New external API integrations

This is not a gatekeeping policy — it exists because these components have subtle interdependencies and calibration decisions that require architectural context.

---

## Getting Started

### 1. Fork and clone

```bash
git clone https://github.com/your-org/kulima-flex.git
cd kulima-flex
```

### 2. Set up your environment

```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
cp .env.example .env         # Add your API keys
```

### 3. Run the test suite

```bash
pytest
```

All tests must pass before submitting a pull request.

### 4. Run the application

```bash
streamlit run app.py
```

---

## Development Workflow

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Write your code with tests.

3. Run the full test suite and confirm all tests pass:
   ```bash
   pytest -v
   ```

4. Write or update relevant documentation in `docs/`.

5. Open a pull request against `main` with a clear description of what the change does and why.

---

## Code Style

- Python 3.11+
- Type annotations on all public functions and methods
- Module-level docstrings on every new file
- Class-level docstrings on every new class
- No bare `except:` clauses — catch specific exception types
- No hardcoded API keys, credentials, or paths — use `kulima/config.py` and environment variables
- Use `pydantic` for data model definitions, not plain dicts or dataclasses, for anything that crosses module boundaries

---

## Testing

Tests live in the root `tests/` directory (or in the root alongside `app.py` for historical reasons). We use `pytest`.

- Every new module should have a corresponding test file
- Tests must not make live API calls — mock external services
- Tests must not depend on an existing `founders.db` — use in-memory or temp databases

```bash
pytest                    # Run all tests
pytest -v                 # Verbose output
pytest test_thesis_engine.py  # Run a single test file
```

---

## Terminology

When writing code, documentation, or commit messages, use Kulima FLEX's product vocabulary:

| Use | Avoid |
|---|---|
| Investment Intelligence Operating System | AI startup scorer |
| Trust Layer | Trust system |
| Evidence Integrity Engine | Evidence checker |
| Reliability Rating | Trust score |
| Evidence Depth | Evidence amount |
| Evidence Consistency | Conflict check |
| Recommendation | AI decision |
| Twin Syndicate | AI debate |
| Continental Futures | Scenario simulator |
| Portfolio Intelligence | Deal tracker |

---

## Commit Messages

Use conventional commits:

```
feat: add pitch deck ingestion to founder agent context
fix: correct evidence depth calculation for sparse OSINT results
docs: add trust-layer architecture specification
test: add unit tests for thesis engine evidence fit
refactor: extract IC prompt formatting to memo_agent helpers
```

---

## Reporting Issues

When reporting a bug, please include:
- Python version and OS
- The exact error message and stack trace
- The step that triggered the error (what you entered in the UI, which tab, etc.)
- Whether the issue is reproducible with `pytest` or only in the live app

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
