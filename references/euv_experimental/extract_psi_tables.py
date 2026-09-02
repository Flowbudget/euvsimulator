#!/usr/bin/env python3
"""Q2 (PSI): Tabellenwerte gezielt extrahieren (Table 2/3/4 + Fig. 6 Kontext)."""
import csv
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
TXT = BASE / "source_02_psi_resist_screening" / "extracted_data" / "fulltext.txt"
OUT = BASE / "source_02_psi_resist_screening" / "extracted_data"

text = TXT.read_text(encoding="utf-8")
lines = text.splitlines()

# Tabellen-Regionen finden (Table X bis nächste Abbildung/Überschrift)
for tname in ["Table 2", "Table 3", "Table 4"]:
    idxs = [i for i, l in enumerate(lines) if tname in l]
    print(f"== {tname}: {len(idxs)} Vorkommen ==")
    for i in idxs:
        # 1 Zeile vor bis 12 Zeilen nach
        chunk = lines[max(0, i - 1):i + 14]
        print("   " + " | ".join(c.strip() for c in chunk if c.strip()))

# Fig. 6: LWR vs dose Kontext
print("\n== Fig. 6 (LWR vs dose) Kontext ==")
for i, l in enumerate(lines):
    if "unbiased LWR vs. dose" in l or "Figure 6" in l:
        chunk = lines[max(0, i - 1):i + 12]
        print("   " + " | ".join(c.strip() for c in chunk if c.strip()))
        break
