# Contributing to OpEnUV

Thank you for your interest in contributing to OpEnUV, the open-source EUV lithography simulator. We welcome contributions of all kinds — bug reports, feature requests, documentation improvements, and code changes.

## Table of Contents

- [Development Environment](#development-environment)
- [Coding Standards](#coding-standards)
- [Pull Request Process](#pull-request-process)
- [Testing Requirements](#testing-requirements)
- [License and DCO](#license-and-dco)

## Development Environment

1. **Clone the repository:**

   ```bash
   git clone https://github.com/your-org/OpEnUV.git
   cd OpEnUV
   ```

2. **Create a virtual environment:**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install the package in editable mode with dev dependencies:**

   ```bash
   pip install -e ".[dev]"
   ```

4. **Verify the installation:**

   ```bash
   pytest
   ```

## Coding Standards

OpEnUV follows strict coding standards to maintain consistency and readability:

- **Docstrings**: All public modules, classes, functions, and methods must have [numpydoc](https://numpydoc.readthedocs.io/) style docstrings.
- **Formatting**: Code is formatted with [Black](https://black.readthedocs.io/), line length 100.
- **Linting**: [Ruff](https://docs.astral.sh/ruff/) is used for linting. Run `ruff check src/` before committing.
- **Type Hints**: All function signatures must include type annotations. Run `mypy src/` to verify.
- **Imports**: Imports should be organized per Ruff rules. Run `ruff check --fix src/` to auto-fix.

Before submitting, ensure your code passes:

```bash
black --check src/ tests/
ruff check src/ tests/
mypy src/
```

## Pull Request Process

1. **Create a feature branch** from `main`:

   ```bash
   git checkout -b feat/your-feature-name
   ```

2. **Make your changes** following the coding standards above.

3. **Write or update tests** — see [Testing Requirements](#testing-requirements).

4. **Run the full test suite** and ensure all tests pass:

   ```bash
   pytest
   ```

5. **Commit your changes** with a descriptive commit message:

   ```bash
   git commit -m "feat: add support for ..."
   ```

6. **Push your branch and open a Pull Request** against `main`. In the PR description, explain what your changes do and why they are needed.

7. **Address review feedback** — a maintainer will review your PR. Please respond to comments and make requested changes.

8. **Merge** — once approved, a maintainer will merge your PR.

## Testing Requirements

- All new code must be covered by tests.
- We use [pytest](https://docs.pytest.org/) as the test framework.
- Test files live in the `tests/` directory and follow the naming convention `test_*.py`.
- Run the full suite before submitting:

  ```bash
  pytest --cov=src
  ```

- For bug fixes, include a test that reproduces the original bug.
- For new features, include tests that cover normal operation, edge cases, and error handling.

## License and DCO

By contributing to OpEnUV, you agree that your contributions will be licensed under the [Apache License, Version 2.0](LICENSE).

This project requires **Developer Certificate of Origin (DCO)** sign-off on every commit. To sign off, use the `-s` flag when committing:

```bash
git commit -s -m "feat: my contribution"
```

This adds a `Signed-off-by: Your Name <your.email@example.com>` line to the commit message, certifying that you have the right to submit the contribution under the project's license.

For more information, see [developercertificate.org](https://developercertificate.org/).