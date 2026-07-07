"""
OpEnUV documentation root.

Build with::

    pip install -e ".[dev]"
    sphinx-build docs/ docs/_build/
"""

project = "euv"
copyright = "2026, OpEnUV Contributors"
author = "OpEnUV Contributors"
release = "0.1.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx_rtd_theme",
]

templates_path = ["_templates"]
exclude_patterns = ["_build"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
