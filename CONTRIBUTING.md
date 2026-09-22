# Contributing

```bash
git clone https://github.com/abhibansal60/tidy && cd tidy
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m unittest discover -s tests
```

- Read [AGENTS.md](AGENTS.md) (project rules), [CONTEXT.md](CONTEXT.md) (vocabulary) and [docs/adr](docs/adr) first.
- Jev makes judgments; code owns arithmetic, policy, persistence and every side effect. New account changes need a dry
  run, a separate write token, a live recheck and a test.
- Tests use synthetic data only. Never commit anything from `.tidy/`, `data/`, `secrets/` or `.env`.
- Keep changes small and add one test that fails without them.

Releasing (maintainers): bump `__version__` in `tidy/__init__.py`, add a CHANGELOG entry, push a `vX.Y.Z` tag. The
Release workflow tests, builds and publishes to PyPI via Trusted Publishing.
