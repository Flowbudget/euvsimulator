# OpEnUV Completion Plan — Vervollständigung des EUV-Lithografie-Simulators

## Status Quo (2026-07-20)

**Kern-Pipeline: ✅ FERTIG & VALIDIERT**
- 522/522 Tests grün
- NILS-Validierung gegen unabhängiges Referenzmodell (Diff < 0.03)
- Wissenschaftlich korrekte Physik (Hopkins TCC, SE-Blur, Dosisabhängigkeit)
- Alle Parameter über `SimulationConfig` + CLI einstellbar

---

## Phase 1: Resist-Kette vollständig parametrisierbar machen (Priorität: HOCH)

### 1.1 `full_chem` Resist-Parameter in `SimulationConfig` exposen
```python
# NEU in SimulationConfig:
# Dill ABC exposure
dill_A: float = 0.05      # Absorptionskoeffizient [µm⁻¹]
dill_B: float = 0.0       # Bleich-Koeffizient
dill_C: float = 0.05      # Photosäure-Generierung (Default 0.1)
dill_Q: float = 1.0       # Quantenausbeute (NEU, war hardcoded 1.0)

# PEB (ADI)
peb_D: float = 5.0        # Diffusion [nm²/s]
peb_k: float = 0.3        # Reaktionsrate [1/s]
peb_t_bake: float = 60.0  # Backzeit [s]
peb_sigma_diff: float = 5.0  # Analytischer PEB Diffusions-Sigma [nm]

# Mack Development
mack_R_max: float = 100.0
mack_R_min: float = 0.1
mack_n: float = 5.0
mack_M_th: float = 0.5
```

### 1.2 `_cd_via_full_chem` diese Config-Parameter nutzen (statt Hardcodes)
- `dose_to_acid(C=dill_C, Q=dill_Q, ...)`
- `reaction_diffusion_adi(..., D=peb_D, k=peb_k, n_steps=...)`
- `MackModel(R_max=..., R_min=..., n=..., M_th=...)`

### 1.3 CLI-Optionen für `full_chem` Parameter
```bash
euv simulate --resist-model=full_chem --dill-C=0.1 --dill-Q=0.5 --peb-k=0.2 --peb-t=90 --mack-Rmax=200 ...
```

### 1.4 Validierungstest: `full_chem` vs. `aerial_threshold` Konsistenz
- Bei kalibrierten Parametern sollen beide Pfade ähnliche CDs liefern
- Test in `test_reference_nils.py` ergänzen

---

## Phase 2: Stöckastik in Haupt-Pipeline integrieren (Priorität: MITTEL)

### 2.1 `stochastic.py` Funktionen in Pipeline einbinden
```python
# In run_simulation() nach aerial Image:
if cfg.enable_stochastic:
    aerial = add_photon_shot_noise(aerial, dose=cfg.dose_mj_cm2, ...)
    # oder: aerial = add_resist_stochastics(aerial, ...)
```

### 2.2 Config-Felder
```python
enable_stochastic: bool = False
photons_per_nm2: float = 1e4  # für Shot-Noise
ler_sigma_nm: float = 1.0     # Line Edge Roughness
lwr_sigma_nm: float = 1.5     # Line Width Roughness
```

### 2.3 CLI
```bash
euv simulate --stochastic --photons=1e4 --ler=1.2
```

### 2.4 Output: LER/LWR Statistiken in `SimulationResult`
```python
ler_nm: float = 0.0
lwr_nm: float = 0.0
cd_distribution: List[float] = []  # bei Monte-Carlo runs
```

---

## Phase 3: Prozess-Fenster / Bossung automatisiert & visualisiert (Priorität: MITTEL)

### 3.1 `process-window` CLI erweitern
- `--output-csv` für Excel-Import
- `--output-plot` für PNG (Heatmap CD über Dose×Fokus)
- `--tolerance=±10%` einstellbar
- `--target-cd` Default aus Config

### 3.2 `SimulationResult` um Process-Window Metriken erweitern
```python
depth_of_focus_nm: float = 0.0
exposure_latitude_pct: float = 0.0
meef: float = 0.0  # Mask Error Enhancement Factor
```

### 3.3 MEFF Berechnung
```python
# MEFF = (ΔCD_wafer / CD_wafer) / (ΔCD_mask / CD_mask)
# ≈ d(CD)/d(mask_CD) * (mask_CD / wafer_CD)
# Numerisch über zwei Simulationen mit leicht variiertem mask_CD
```

---

## Phase 4: Mask-3D / RCWA Integration (Priorität: NIEDRIG bis MITTEL)

### 4.1 `mask3d/rcwa.py` in Pipeline einbinden
- Statt Fourier-Koeffizienten analytisch (a, b, c₀) → RCWA für echte Masken-Topographie
- Parameter: `absorber_height`, `absorber_taper`, `undercut`, `multilayer_roughness`

### 4.2 Config
```python
use_rcwa: bool = False
mask_absorber_taper_deg: float = 0.0
mask_undercut_nm: float = 0.0
mask_sidewall_roughness_nm: float = 0.0
```

### 4.3 Validierung: RCWA vs. analytisch für Thin-Mask-Limit
- Test: `use_rcwa=False` (analytisch) vs. `use_rcwa=True` mit dünnem Absorber → Diff < 1%

---

## Phase 5: High-NA EUV (Priorität: FORSCHUNG)

### 5.1 `high_na.py` Module nutzen
- Anamorphotisches Pupillen (NA_x ≠ NA_y)
- Polarisation (TE/TM) in TCC
- Zernike-Aberrationen

### 5.2 Config
```python
high_na_mode: bool = False
na_x: float = 0.55
na_y: float = 0.55 * 0.5  # Anamorphose 4x/8x
polarisation: str = "unpolarized"  # "TE", "TM", "unpolarized"
zernike_coeffs: List[float] = []   # [Z4, Z5, Z6, ...] Wellenfront-Fehler
```

### 5.3 CLI
```bash
euv simulate --high-na --na-x=0.55 --na-y=0.275 --polarisation=TE --zernike="0,0,0.02,0,0"
```

---

## Phase 6: Dokumentation & Lehre-Material (Priorität: HOCH für Uni-Einsatz)

### 6.1 Jupyter Notebooks für Lehrveranstaltungen
| Notebook | Thema |
|----------|-------|
| `01_aerial_image.ipynb` | Hopkins vs. Abbe, TCC, Kohärenz, SE-Blur |
| `02_nils_cd.ipynb` | NILS Definition, Messung, CD-Abhängigkeit |
| `03_resist_chain.ipynb` | Dill ABC, PEB, Mack, Dosis-Latitude |
| `04_process_window.ipynb` | Bossung, DoF, EL, MEFF |
| `05_stochastics.ipynb` | Photon Shot Noise, LER, LWR |
| `06_mask3d.ipynb` | RCWA, Mask-3D-Effekte, Best Focus Shift |

### 6.2 Parameter-Guide (Markdown/PDF)
- Jeder Parameter: Physikalische Bedeutung, typischer Bereich, Literatur-Referenz
- "Was passiert wenn ich X ändere?" Cheat-Sheet

### 6.3 Validierungs-Bericht (bereits in Obsidian)
- Erweitern um: Alle Phasen, bekannte Limitationen, Referenz-Literatur

---

## Phase 7: CI/CD & Release-Qualität (Priorität: BETRIEB)

### 7.1 GitHub Actions
- `pytest` auf Ubuntu (CPU) + macOS (ARM)
- `pytest --cov` Coverage-Report
- Wheels bauen (Linux x86_64, macOS ARM64, Windows x86_64)

### 7.2 PyPI Release Process
- `pyproject.toml` version bump
- `git tag v1.1.0`
- `pip publish` automation

### 7.3 Benchmarks im CI
- Performance-Regression-Test (Walltime < X sec für Standard-Config)
- VRAM-Schätzung validieren

---

## Aufwandsschätzung

| Phase | Aufwand | Dauer (1 Person) | Abhängigkeiten |
|-------|---------|------------------|----------------|
| 1: Resist Config | ~2 Tage | 1 Woche | — |
| 2: Stöckastik | ~3 Tage | 1 Woche | Phase 1 |
| 3: Process Window | ~2 Tage | 3 Tage | — |
| 4: RCWA Integration | ~5 Tage | 2 Wochen | Mask3D Modul stabil |
| 5: High-NA | ~5 Tage | 2 Wochen | High-NA Modul stabil |
| 6: Lehre-Notebooks | ~5 Tage | 1-2 Wochen | Alle Phasen |
| 7: CI/CD | ~2 Tage | 3 Tage | — |

**Gesamt: ~24 Tage ≈ 5 Wochen für "Feature-Complete v1.2"**

---

## Empfohlene Reihenfolge

1. **Phase 1** (Resist Config) — macht `full_chem` nutzbar & reproduzierbar
2. **Phase 3** (Process Window) — sofort nützlich für Prozess-Engineering
3. **Phase 2** (Stochastik) — für fortgeschrittene Kurse / LER-Studien
4. **Phase 6** (Notebooks) — parallel laufend, für Lehre essenziell
5. **Phase 4/5** — forschungsnah, auf Bedarf
6. **Phase 7** — vor erstem öffentlichen Release