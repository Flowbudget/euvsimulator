"""Tests for release preparation files."""

from pathlib import Path

import tomllib

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_changelog_exists():
    """CHANGELOG.md exists and has expected format."""
    path = PROJECT_ROOT / "CHANGELOG.md"
    assert path.exists(), f"{path} does not exist"
    content = path.read_text()
    assert "# Changelog" in content, "Missing # Changelog header"
    assert "## v0.1.0" in content, "Missing v0.1.0 entry"
    assert "Initial public release" in content
    assert "Apache-2.0" in content


def test_contributing_exists():
    """CONTRIBUTING.md exists."""
    path = PROJECT_ROOT / "CONTRIBUTING.md"
    assert path.exists(), f"{path} does not exist"
    content = path.read_text()
    assert "Contributing to OpEnUV" in content
    assert "DCO" in content or "Developer Certificate" in content
    assert "Apache" in content or "Apache-2.0" in content


def test_code_of_conduct_exists():
    """CODE_OF_CONDUCT.md exists."""
    path = PROJECT_ROOT / "CODE_OF_CONDUCT.md"
    assert path.exists(), f"{path} does not exist"
    content = path.read_text()
    assert "Contributor Covenant" in content
    assert "Code of Conduct" in content


def test_security_exists():
    """SECURITY.md exists."""
    path = PROJECT_ROOT / "SECURITY.md"
    assert path.exists(), f"{path} does not exist"
    content = path.read_text()
    assert "Security" in content or "security" in content
    assert "Reporting" in content or "reporting" in content


def test_manifest_in_exists():
    """MANIFEST.in exists with expected includes."""
    path = PROJECT_ROOT / "MANIFEST.in"
    assert path.exists(), f"{path} does not exist"
    content = path.read_text()
    assert "include src/euv/data/henke/*.nff" in content
    assert "include LICENSE" in content
    assert "include README.md" in content


def test_pyproject_has_classifiers():
    """pyproject.toml contains project.classifiers."""
    path = PROJECT_ROOT / "pyproject.toml"
    assert path.exists(), f"{path} does not exist"
    data = tomllib.loads(path.read_text())
    classifiers = data.get("project", {}).get("classifiers", [])
    assert len(classifiers) >= 7, f"Expected at least 7 classifiers, got {len(classifiers)}"
    expected = [
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Topic :: Scientific/Engineering",
        "Intended Audience :: Science/Research",
    ]
    for exp in expected:
        assert exp in classifiers, f"Missing classifier: {exp}"
    for ver in ("3.10", "3.11", "3.12"):
        assert f"Python :: {ver}" in str(classifiers), f"Missing classifier for Python {ver}"


def test_pyproject_has_urls():
    """pyproject.toml contains project.urls."""
    path = PROJECT_ROOT / "pyproject.toml"
    data = tomllib.loads(path.read_text())
    urls = data.get("project", {}).get("urls", {})
    expected_keys = ["Homepage", "Repository", "Documentation", "Issues"]
    for key in expected_keys:
        assert key in urls, f"Missing [project.urls] key: {key}"


def test_pyproject_has_include_package_data():
    """pyproject.toml enables package data inclusion under [tool.setuptools]."""
    path = PROJECT_ROOT / "pyproject.toml"
    data = tomllib.loads(path.read_text())
    tool = data.get("tool", {})
    setuptools = tool.get("setuptools", {})
    # Modern setuptools uses the hyphenated key "include-package-data";
    # accept either spelling.
    include = setuptools.get("include-package-data", setuptools.get("include_package_data", False))
    assert include is True, "include-package-data is not true in [tool.setuptools]"


def test_all_release_files_exist():
    """All expected release files exist."""
    for name in [
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "SECURITY.md",
        "MANIFEST.in",
    ]:
        path = PROJECT_ROOT / name
        assert path.exists(), f"Missing release file: {name}"
