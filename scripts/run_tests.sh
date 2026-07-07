#!/bin/bash
# Install dependencies and run all tests for OpEnUV
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== OpEnUV Full Test Suite ==="
echo "Python: $(python3 --version)"
echo "PyTorch: $(python3 -c 'import torch; print(torch.__version__)')"
echo ""

# Install package
pip install -e ".[dev]" -q

# Run tests with coverage
python -m pytest tests/ -v \
    --tb=short \
    --cov=src/euv \
    --cov-report=term-missing \
    --cov-report=html:coverage_html \
    -x 2>&1

echo ""
echo "=== All tests completed ==="
