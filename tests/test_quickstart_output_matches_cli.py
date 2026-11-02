"""The documented output of ``euv simulate`` must match what the CLI prints.

docs/quickstart.rst carries the expected JSON block; the default run prints
27.62 / 4.9685 / 0.3299 / 17.9987 plus ler_nm, lwr_nm and the configuration.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from typer.testing import CliRunner

from euvsimulator.io.cli import app

PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUICKSTART = PROJECT_ROOT / "docs" / "quickstart.rst"


def _expected_output_block() -> dict:
    """The JSON code block that follows 'Expected output' in quickstart.rst."""
    text = QUICKSTART.read_text(encoding="utf-8")
    m = re.search(
        r"Expected output.*?\.\. code-block:: json\n\n((?:[ \t]+[^\n]*\n|\n)+)", text, re.DOTALL
    )
    assert m, "quickstart.rst: no JSON block after 'Expected output'"
    return json.loads(m.group(1))


def test_quickstart_expected_output_matches_cli() -> None:
    """The documented output of plain ``euv simulate`` is what the CLI prints."""
    result = CliRunner().invoke(app, ["simulate"])
    assert result.exit_code == 0, result.output
    printed = json.loads(result.output[result.output.index("{") :])
    assert _expected_output_block() == printed
