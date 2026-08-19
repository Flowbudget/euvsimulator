# Sphinx build configuration for euvsimulator docs

import os
import sys

sys.path.insert(0, os.path.abspath("../../src"))

project = "euvsimulator"
copyright = "2026, euvsimulator Contributors"
author = "euvsimulator Contributors"
release = "1.0.3"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.mathjax",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx_rtd_theme",
]

templates_path = ["_templates"]
# Notebooks ship in docs/tutorials/ as standalone runnable examples.
# They are excluded from the Sphinx build to keep it pandoc-free.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "**.ipynb_checkpoints", "tutorials/*.ipynb"]

html_theme = "sphinx_rtd_theme"
html_static_path = []

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "torch": ("https://pytorch.org/docs/stable", None),
    "numpy": ("https://numpy.org/doc/stable", None),
}

napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True

autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}

nbsphinx_allow_errors = True

# Do not execute notebooks at doc-build time — they are illustrative examples
# and requiring a live Jupyter kernel would make the docs build fragile.
nbsphinx_execute = "never"

# Suppress known RST warnings from subagent-generated docstrings
suppress_warnings = [
    "ref.footnote",
    "docutils",
]