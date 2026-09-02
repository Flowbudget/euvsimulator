#!/usr/bin/env python3
"""Extrahiere quantitative Daten aus den archivierten EUV-Referenzquellen.

Nur LESEN + strukturierte CSV/JSON-Ausgabe in extracted_data/.
Keine Werte erfinden; Grafikwerte werden als digitized_from_figure markiert.
"""
import csv
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent  # references/euv_experimental/

# ── Quelle 2: PSI-PDF ────────────────────────────────────────────
def extract_psi_pdf():
    src = BASE / "source_02_psi_resist_screening" / "original" / "Develioglu-2023-EUV_lithography_resist_screening.pdf"
    out = BASE / "source_02_psi_resist_screening" / "extracted_data"
    out.mkdir(parents=True, exist_ok=True)
    text = ""
    try:
        import fitz  # pymupdf
        doc = fitz.open(str(src))
        for page in doc:
            text += f"\n--- PAGE {page.number + 1} ---\n" + page.get_text()
    except ImportError:
        print("  [pymupdf fehlt — PDF-Text nicht extrahierbar]")
        return
    (out / "fulltext.txt").write_text(text, encoding="utf-8")
    print(f"  PDF-Text extrahiert: {len(text)} Zeichen, {len(doc)} Seiten")

    # Metadaten: erste 3 Seiten für Titel/Autoren/Jahr/DOI
    head = text[:2500]
    print("  VORSPANN (erste 1200 Zeichen):")
    print("  " + head[:1200].replace("\n", " | "))

    # Kandidaten-Tabellen: Zeilen mit Zahlenmustern (Dosis/CD/LWR)
    rows = []
    for line in text.splitlines():
        ls = line.strip()
        if re.search(r"\d+(\.\d+)?\s*(mJ|nm|µC|uC)", ls) and len(ls) < 200:
            rows.append(ls)
    (out / "number_lines.txt").write_text("\n".join(rows), encoding="utf-8")
    print(f"  Zeilen mit Zahlen+Einheiten: {len(rows)} (siehe number_lines.txt)")

    # DOI/Journal-Suche
    doi = re.findall(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", text, re.I)
    print(f"  DOI-Kandidaten: {doi[:5]}")

# ── Quelle 1: PMC-HTML ───────────────────────────────────────────
def extract_pmc_html():
    src = BASE / "source_01_pmma_euv" / "original" / "PMC8979033.html"
    out = BASE / "source_01_pmma_euv" / "extracted_data"
    out.mkdir(parents=True, exist_ok=True)
    html = src.read_text(encoding="utf-8", errors="ignore")

    # Tabellen aus dem HTML ziehen (PMC nutzt <table>)
    tables = re.findall(r"<table.*?</table>", html, re.S)
    print(f"  HTML-Tabellen gefunden: {len(tables)}")
    all_rows = []
    for ti, tbl in enumerate(tables, 1):
        rows = re.findall(r"<tr.*?</tr>", tbl, re.S)
        cells = []
        for r in rows:
            cs = re.findall(r"<(td|th)[^>]*>(.*?)</\1>", r, re.S)
            cells.append([re.sub(r"<[^>]+>", "", c[1]).strip() for c in cs])
        all_rows.append((ti, cells))
        (out / f"table_{ti:02d}.csv").write_text(
            "\n".join(",".join(c) for c in cells), encoding="utf-8"
        )
        print(f"    Tabelle {ti}: {len(cells)} Zeilen -> table_{ti:02d}.csv")

    # Keyword-Kontext für quantitative Aussagen
    kw = re.compile(r"(dose|CD|LER|sensitivity|contrast|thickness|mJ/cm2|mJ cm-2|nm\b)", re.I)
    hits = []
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    for m in kw.finditer(text):
        s = max(0, m.start() - 80)
        hits.append(text[s:m.end() + 120])
    (out / "keyword_context.txt").write_text("\n".join(hits[:200]), encoding="utf-8")
    print(f"  Keyword-Kontexte: {len(hits)} (gekappt auf 200)")

    # Metadaten (Meta-Tags)
    meta = {}
    for pat, key in [
        (r'<meta name="citation_title" content="(.*?)"', "title"),
        (r'<meta name="citation_author" content="(.*?)"', "author"),
        (r'citation_publication_date.*?content="(.*?)"', "date"),
        (r'citation_doi.*?content="(.*?)"', "doi"),
        (r'<meta name="citation_journal_title" content="(.*?)"', "journal"),
    ]:
        m = re.search(pat, html, re.S)
        if m:
            meta[key] = m.group(1).strip()
    (out / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"  Metadaten: {meta}")

if __name__ == "__main__":
    print("== Extraktion Quelle 2 (PSI PDF) ==")
    extract_psi_pdf()
    print("\n== Extraktion Quelle 1 (PMC HTML) ==")
    extract_pmc_html()
    print("\nFERTIG")
