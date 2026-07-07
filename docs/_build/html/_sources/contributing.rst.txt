Contributing
============

We welcome contributions!  Please see our guidelines:

Code of Conduct
---------------

We follow the `Contributor Covenant <https://www.contributor-covenant.org/>`_.

Getting Started
---------------

1. Fork the repository
2. Install in editable mode: ``pip install -e ".[dev]"``
3. Run tests: ``pytest -q``
4. Format: ``black src/euv/ tests/``
5. Lint: ``ruff check src/euv/ tests/``

Pull Request Process
--------------------

- All tests must pass
- New features include tests
- Docstrings follow NumPy/Google style
- Keep ``src/euv/`` 100 % Apache-2.0-compatible

License
-------

Apache-2.0 — see ``LICENSE``.
