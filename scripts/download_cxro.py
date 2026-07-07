#!/usr/bin/env python3
"""Download CXRO/Henke atomic scattering factor tables for all 92 elements.

The CXRO/Henke tables contain f1, f2 atomic scattering factors from
10 eV to 30 keV for all elements Z=1–92.

Usage::

    python scripts/download_cxro.py

Downloads ``sf.tar.gz`` (~500 KB) from henke.lbl.gov and extracts
``*.nff`` files to ``data/cxro/``.

References
----------
https://henke.lbl.gov/optical_constants/asf.html
B.L. Henke, E.M. Gullikson, J.C. Davis, Atomic Data and Nuclear
Data Tables 54(2), 181–342 (1993).
"""

from __future__ import annotations

import csv
import io
import tarfile
from pathlib import Path

import httpx

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "cxro"
CXRO_URL = "https://henke.lbl.gov/optical_constants/sf.tar.gz"

# EUV-relevant elements + their Z for reference
CORE_ELEMENTS = {
    42: "Mo",
    14: "Si",
    44: "Ru",
    73: "Ta",
    50: "Sn",
    6: "C",
    24: "Cr",
    13: "Al",
    28: "Ni",
    79: "Au",
    40: "Zr",
    4: "Be",
    41: "Nb",
    12: "Mg",
    22: "Ti",
}


def convert_nff_to_csv(content: str | Path, csv_path: Path) -> int:
    """Convert an .nff (tabbed) file to standard CSV.

    *content* can be a file path or a raw string.
    Returns number of rows written.
    """
    rows = 0
    if isinstance(content, str) and "\n" in content:
        # Raw string content
        lines = content.splitlines()
    else:
        lines = open(content).readlines()

    with open(csv_path, "w", newline="") as fout:
        writer = csv.writer(fout)
        writer.writerow(["energy_eV", "f1", "f2"])
        for line in lines:
            line = line.strip()
            if not line or line.startswith("E(eV)") or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 3:
                try:
                    energy = float(parts[0])
                except ValueError:
                    continue  # skip header lines
                f1_val = None if parts[1].strip() == "-9999." else float(parts[1])
                writer.writerow(
                    [
                        float(parts[0]),
                        f1_val,
                        float(parts[2]),
                    ]
                )
                rows += 1
    return rows


def download_and_extract(client: httpx.Client) -> int:
    """Download sf.tar.gz, extract .nff files, convert to CSV.

    Returns number of elements processed.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {CXRO_URL}...")
    resp = client.get(CXRO_URL, timeout=60, follow_redirects=True)
    if resp.status_code != 200:
        print(f"  ✗ HTTP {resp.status_code}")
        return 0

    count = 0
    with tarfile.open(fileobj=io.BytesIO(resp.content), mode="r:gz") as tar:
        for member in tar.getmembers():
            if not member.name.endswith(".nff"):
                continue
            element = Path(member.name).stem  # e.g. "mo.nff" -> "mo"
            element_cap = element.capitalize()  # "Mo"

            # Extract to temp, convert to CSV
            f = tar.extractfile(member)
            if f is None:
                continue
            content = f.read().decode("ascii", errors="replace")

            csv_path = DATA_DIR / f"{element_cap}.csv"
            rows = convert_nff_to_csv(content, csv_path)

            if rows > 0:
                print(f"  ✓ {element_cap}: {rows} rows -> {csv_path.name}")
                count += 1
            else:
                print(f"  - {element_cap}: empty file, skipped")

    return count


def main():
    """Download all CXRO Henke scattering-factor tables into the data dir."""
    with httpx.Client() as client:
        count = download_and_extract(client)

    print(f"\nDone: {count} elements extracted to {DATA_DIR}")


if __name__ == "__main__":
    main()
