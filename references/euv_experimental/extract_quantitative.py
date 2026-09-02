#!/usr/bin/env python3
"""STEP 5.2C — READ-ONLY: Quantitative Werte aus den Archivquellen extrahieren.

Nur Lesen der archivierten Originale. KEINE Änderungen.
"""
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent

# ── Q1: PMC-HTML — konkrete Zahlen (Text, nicht Figuren) ────────
print("=" * 70)
print("QUELLE 1: PMMA (PMC8979033.html) — Zahlen im Text")
print("=" * 70)
html = (BASE / "source_01_pmma_euv" / "original" / "PMC8979033.html").read_text(encoding="utf-8", errors="ignore")
text = re.sub(r"<[^>]+>", " ", html)
text = re.sub(r"\s+", " ", text)

patterns = [
    (r"LER of [^.]{0,80}", "LER-Aussage"),
    (r"line edge roughness[^.]{0,120}", "LER-Kontext"),
    (r"critical dimension[^.]{0,100}", "CD-Kontext"),
    (r"dose-to-clear[^.]{0,120}", "DCT-Kontext"),
    (r"sensitivity of[^.]{0,100}", "Sensitivity"),
    (r"contrast of[^.]{0,100}", "Contrast"),
    (r"\d+(\.\d+)?\s*mJ cm.{0,40}", "Dosiswert"),
    (r"\d+(\.\d+)?\s*mJ/cm.{0,40}", "Dosiswert2"),
]
seen = set()
for pat, label in patterns:
    for m in re.finditer(pat, text, re.I):
        s = m.group(0).strip()
        if s not in seen and len(s) > 10:
            seen.add(s)
            print(f"  [{label}] {s[:160]}")

# Absorption / wellenlänge / dicke explizit
for pat, label in [
    (r"13\.5\s*nm", "Wellenlänge"),
    (r"160\s*nm thick", "Dicke"),
    (r"absorb[^.]{0,60}", "Absorption"),
    (r"\d+\s*µm|um", "µm"),
]:
    for m in re.finditer(pat, text, re.I):
        s = m.group(0).strip()
        if s not in seen:
            seen.add(s)
            print(f"  [{label}] {s[:120]}")

# ── Q2: PSI-PDF — LWR-Zahlen aus Tabellen-Kontext ───────────────
print()
print("=" * 70)
print("QUELLE 2: PSI (PDF) — LWR/Z-Kontext")
print("=" * 70)
pdftext = (BASE / "source_02_psi_resist_screening" / "extracted_data" / "fulltext.txt").read_text(encoding="utf-8")
# Zeilen rund um LWR-Werte (nm-Angaben in Tabellenzeilen)
for i, line in enumerate(pdftext.splitlines()):
    ls = line.strip()
    if re.search(r"LWR|lwr", ls, re.I) and re.search(r"\d", ls):
        print(f"  L{ls[:150]}")
