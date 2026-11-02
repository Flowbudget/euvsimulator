"""scripts/download_cxro.py must write where euvsimulator.materials reads.

Before the fix the script wrote to <repo>/data/cxro, a directory nothing reads,
so the advice in CXROTable's FileNotFoundError ("Run python
scripts/download_cxro.py first") could not fix the error.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

import euvsimulator.materials as materials
from euvsimulator.materials import CXROTable

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "download_cxro.py"


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_script_data_dir_is_loader_data_dir():
    """The script's DATA_DIR is the directory CXROTable() reads by default."""
    module = _load_script("_download_cxro_default")
    script_dir = Path(module.DATA_DIR).resolve()
    assert script_dir == Path(materials.DATA_DIR).resolve()
    assert script_dir == Path(CXROTable()._data_dir).resolve()
    assert script_dir != (ROOT / "data" / "cxro").resolve()


def test_script_data_dir_fallback_without_package(monkeypatch):
    """Without an importable package the script falls back to the source tree."""
    monkeypatch.setitem(sys.modules, "euvsimulator.materials", None)
    module = _load_script("_download_cxro_fallback")
    expected = ROOT / "src" / "euvsimulator" / "data" / "cxro"
    assert Path(module.DATA_DIR).resolve() == expected.resolve()
    assert (expected / "Mo.csv").is_file()


def test_converted_csv_is_readable_by_loader(tmp_path):
    """convert_nff_to_csv writes the format CXROTable reads (-9999. -> empty f1)."""
    module = _load_script("_download_cxro_convert")
    nff = "E(eV)\tf1\tf2\n10.0\t-9999.\t2.0\n90.0\t5.0\t1.0\n100.0\t7.0\t3.0\n"
    csv_path = tmp_path / "Mo.csv"
    rows = module.convert_nff_to_csv(nff, csv_path)
    assert rows == 3
    lines = csv_path.read_text().splitlines()
    assert lines[0] == "energy_eV,f1,f2"
    assert lines[1] == "10.0,,2.0"
    table = CXROTable(tmp_path)
    assert table.get_f1f2("Mo", 90.0) == pytest.approx((5.0, 1.0))
    assert table.get_f1f2("Mo", 100.0) == pytest.approx((7.0, 3.0))


def test_shell_script_wraps_python_script():
    """download_cxro.sh delegates to download_cxro.py.

    Before the fix it wrote raw .nff files to src/euv/data/henke, a path and
    format the loader never read.
    """
    sh = ROOT / "scripts" / "download_cxro.sh"
    text = sh.read_text()
    assert "src/euv/" not in text
    assert "download_cxro.py" in text
    subprocess.run(["bash", "-n", str(sh)], check=True)
