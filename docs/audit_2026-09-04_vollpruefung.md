# Vollprüfung euvsimulator — Bericht vom 2026-09-04

**Auftrag:** „prüfe das gesamte Repository auf Fehler … kritisch, analytisch … erstmal nur einen Bericht … ändere keine Physik oder Code … wenn du eine Vermutung hast, mache einen Monkeytest."

**Stand:** `main`, Commit `4075436` (20 Commits vor `origin/main`). **Kein Code, kein Parameter, kein Test verändert.** Alle Messungen per Monkey-Patch durch die echte Pipeline; Skripte im Scratchpad (Liste im Anhang).

**Status-Nachtrag (später am 2026-09-04, Phase 0 umgesetzt — siehe Arbeitslog „Fortsetzung 11"):**
A1 (absorbierte Photonen), A2 (Dosis-Konvention), A5 (Q entfernt), A4-Einheiten (k_Q·G₀),
C3 (tote Parameter), C4 `nominal_dose`, B5-Taper (jetzt `NotImplementedError`) und die
hart codierten Mo/Si-n,k in `geometry.py` sind behoben. Dabei zusätzlich gefunden und behoben:
`dill_B` wurde durch `B, H, W = dose.shape` überschrieben (nie wirksam); RCWA-Ordnungen um eins
falsch beschriftet; RCWA auf Wafer- statt Maskenskala. **Offen:** A3 (σ_diff), A4-Struktur
(Quencher auf Diffusionsskala, beide Pfade), A6, B1, B2, B5-TM, C1, C5.

**Lesart dieses Berichts:** Jeder Befund trägt eine Klasse — **[BESTÄTIGT]** = numerisch oder gegen Primärquelle belegt, **[GELESEN]** = aus dem Code eindeutig ableitbar, aber nicht separat gemessen, **[VERDACHT]** = plausibel, nicht abgeschlossen. Was ich geprüft und für korrekt befunden habe, steht in Abschnitt D, damit „nicht erwähnt" nicht mit „nicht geprüft" verwechselt wird. Eigene Fehleinschätzungen aus diesem Audit stehen in Abschnitt F.

**Testsuite:** `pytest -x -q` auf diesem Stand: **797 passed, 0 failed, 3 warnings, 737,95 s.** Grün heißt hier nur: die Tests prüfen nicht die in A1/A2/A4/A6 beschriebenen Eigenschaften — keiner der kritischen Befunde wird von einem Test erfasst (Abschnitt E, Punkt 7).

---

## A. Kritisch — physikalisch falsch, wirkt direkt auf Kernergebnisse

### A1 [BESTÄTIGT] Photonen-Schrotrauschen wird auf *einfallende* statt *absorbierte* Photonen berechnet

`resist/stochastic.py::photon_deposition_shot_noise` hat einen Parameter `absorption` (Docstring: „Fraction of incident photons absorbed … Default 1.0"). `pipeline.py:1298` ruft die Funktion **ohne** `absorption` auf. Mit `dill_A+dill_B = 1,06/µm` und 50 nm Film werden physikalisch nur `1−exp(−0,053) = 5,2 %` der Photonen absorbiert; nur diese erzeugen Säure (Mack, Biafore & Smith 2011, Exposure Kinetics: n_abs = D·α·V/E_ph). Das Modell zählt 19× zu viele Photonen.

Monkey-Test `audit_absorption.py` (P=44, CD=22, Konfig A = nur Photonenrauschen, 3 Realisierungen, Seed 42):

| σ_PEB | absorption | CD | LWR [nm] | n_eff |
|---|---|---|---|---|
| 7,0 | 1,0 (Repo) | 22,00 | 0,350 | 15,4 |
| 7,0 | **0,0516** | 22,00 | **2,375** | 12,4 |
| 19,9 | 1,0 (Repo) | 22,00 | 1,304 | 9,4 |
| 19,9 | **0,0516** | 22,00 | **10,339** | 8,7 |

Faktor 6,8 bzw. 7,9 (vorhergesagt ≥ 2,5; Erwartung √(1/η) = 4,4, Nichtlinearität verstärkt). CD unverändert (Erwartungswert unverzerrt, wie vorhergesagt). **Folge:** Alle bisherigen Aussagen der Art „Photonenrauschen allein liefert X nm" sind um diesen Faktor zu klein — inklusive der Aussage in Fortsetzung 10, das Photonenrauschen fülle das Zielband „fast" aus. Mit korrekter Absorption liegt reines Photonenrauschen am σ-Optimum bei 2,4 nm (im Zielband 2,17–3,43) und am Default bei 10,3 nm.

Zusätzlich [GELESEN]: das Rauschen wird 2D erzeugt und dann deterministisch über die Tiefe skaliert — alle 21 Schichten teilen dieselbe Realisierung (vollständig z-korreliert). Für das säulenintegrierte Kantenrauschen ist das mit `absorption = 1−e^{−αt}` eine brauchbare erste Näherung, aber keine schichtweise Absorptionsstatistik.

### A2 [BESTÄTIGT] `dose_mj_cm2` ist nicht die Wafer-Dosis in Scanner-Konvention — undokumentiert, und alle Literaturvergleiche sind davon betroffen

Messung (`run_simulation`, dose=1): Aerial-Bild bei P=44: min 0,017, max 0,392, Mittel 0,199; bei P=64 max 0,582. Offene ML-Fläche: |r_space|² = **0,647**. `pipeline.py:1747` skaliert `aerial * dose_mj_cm2`. Das Resist sieht also maximal 0,39·dose und im Mittel 0,20·dose.

In der Lithografie ist die Dosis (mJ/cm²) die Energiedichte **am Wafer im offenen Feld**: E₀ („dose-to-clear") wird mit offener Maske gemessen; der Dill-C-Parameter (cm²/mJ, Yamamoto 2011) ist auf die am Resist ankommende Dosis definiert. Damit `dose_mj_cm2` diese Bedeutung hat, müsste das Aerial-Bild auf clear-field = 1 normiert sein (Division durch |r_space|²). Aktuell ist die effektive Wafer-Dosis **0,647 × Nennwert** (bei Default-ML; sie ändert sich mit `ml_roughness_nm`, `ml_n_bilayers` etc. — ein Scanner kalibriert die Dosis am Wafer nach, das Modell nicht).

Das Feld `dose_mj_cm2: float = 20.0` (pipeline.py:143) hat **keinen** Kommentar; „wafer", „clear field", „open frame" kommen in pipeline.py nicht vor. Die Konvention ist nirgends festgelegt.

**Konsequenzen, die bisherige Schlussfolgerungen umkehren:**
- Dosis-zu-Größe „24 mJ/cm²" entspricht **15,5 mJ/cm² Wafer-Dosis** — *innerhalb* Vesters' 8–16, nicht 40–70 % darüber (Fortsetzung 8/9).
- Der Q-Fix-Preflight (Fortsetzung 10, P1 „erfüllt": 10,5) entspricht **6,8 mJ/cm²** — *unterhalb* Vesters' Bereich. P1 ist damit **nicht** erfüllt. Ich revidiere meine Aussage.
- Der `aerial_threshold`-Pfad ist davon *nicht* betroffen (Schwelle ∝ mean·20/dose, skaleninvariant); der `full_chem`-Pfad und die Photonenzählung sind es.

Hinweis zur Restunsicherheit: ob ASML-Dosiskalibrierung exakt „offene Maske → 1" entspricht, habe ich nicht aus einer Primärquelle belegt; die Definition von E₀ und von Dill-C am Resist ist dagegen Standard. Die Aussage „Konvention undokumentiert und inkonsistent mit den verwendeten Literaturparametern" gilt unabhängig davon.

### A3 [BESTÄTIGT, Fortsetzung 10] PEB-Blur 19,9 nm bei Pitch 44 nm liegt auf der steilen Kontrastverlust-Flanke

Verstärkt jede Rauschquelle ~4× gegenüber σ_tot ≈ P/(2π) (Konfig A 4,0×, Konfig C 3,7×; Pitch-Skalierung bestätigt, P=64: 1,8×). Wert ist Rückrechnung auf Anderson 2009, dessen PSF-Form nicht dokumentiert ist; Quelle für 22-nm-HP nicht gefunden. Details: Arbeitslog Fortsetzung 10, §2–§6.

### A4 [BESTÄTIGT] Quenching im Stochastik-Pfad ist faktisch inert; zusätzlich Einheitenfehler in der Ratenkonstante

- `_reaction_limited_quench` wird auf Voxeln von 0,17×0,17×2,5 nm³ = 0,07 nm³ mit λ_PAG = 0,014 Molekülen ausgewertet. Gemessen (`mean_mismatch.py`): Quencher entfernt 0,3 % der Säure (0,158 → 0,157) bei ⟨q⟩ = 0,25 > ⟨h⟩ = 0,16. Deterministischer Pfad hat gar kein Quenching. Stochastisches CD 26–44 nm gegen deterministisch 22 nm (Fortsetzung 10 §5).
- **Einheiten** [BESTÄTIGT gegen Primärquelle]: Mack 2011 (Quenching, lokal `2011_EUV_Stochastic_Quenching_Kinetics.pdf`, Z. 555): „k_Q·G₀ = 3 s⁻¹" für die Baseline k_Q = 15 nm³/s, G₀ = 0,2/nm³. Für *relative* Konzentrationen h = H/G₀, q = Q/G₀ lautet die Kinetik dh/dt = −(k_Q·G₀)·h·q. `peb.py:454` übergibt `quench_rate = 15` direkt als Rate → **Faktor 5 zu schnell** (15 s⁻¹ statt 3 s⁻¹). Bei t=60 s ist die Reaktion in beiden Fällen vollständig (e^{−90} vs. e^{−18}), der Fehler ist hier numerisch unwirksam — aber die Formulierung ist falsch und würde bei kleinen k_Q oder kurzen Bakes wirksam.

### A5 [GELESEN, Primärquelle in Fortsetzung 9/10] Q-Doppelzählung in `dill_abc_exposure`

`acid = Q·(1−exp(−C·E))` deckelt die Säure bei Q = 0,5; Mack 2013 Gl. 8/10: φ_PAG steckt in C, ⟨h⟩ = 1−e^{−C⟨E⟩}. Preflight ergab: korrigiert die Dosislage, löst das Rauschproblem nicht. Mit A2 ist die Bewertung der Dosislage neu zu machen.

### A6 [BESTÄTIGT] `development_stochasticity` hängt von einem numerischen Parameter ab

`stochastic_development` (develop.py:165) treibt Poisson-Ereignisse mit `drive = (depth − thickness)/thickness`; `depth` ist maximal `thickness + dz` (der bewusst nicht geklemmte „Überschuss", develop.py:388–402). Also `drive ≤ dz/thickness = 1/(N−1)` — eine Funktion von `n_develop_layers`. Monkey-Test `audit_layers.py`:

| N | Konfig A (Photon) | A + development_stochasticity |
|---|---|---|
| 21 | 1,304 nm | 1,438 nm (n_eff 25) |
| 41 | 1,304 nm | **0,168 nm** (n_eff 374, degeneriert) |

Konfig A ist gitterunabhängig; mit `development_stochasticity=True` fällt das LWR bei Halbierung von dz um Faktor 8,5 und *unter* das reine Photonenrauschen — das Modell zerstört dann sogar das vorhandene Rauschen (Binarisierung `e_dev ≥ 0.5` bei rate ≤ 15·0,025 = 0,37 Ereignissen). Das Modell hat keine physikalische Quelle (Docstring: dimensionsloses „strength"), `development_strength = 15` ist Kalibrierparameter. **Zusätzlich** [GELESEN]: `extract_edges` nimmt erstes/letztes unentwickeltes Pixel pro Zeile — isolierte unentwickelte Flecken außerhalb der Linie (die dieses Modell erzeugt) werden als Kante gewertet.

---

## B. Modellgrenzen — teils dokumentiert, teils nicht

### B1 [GELESEN] Entwicklung ist rein vertikal — kein Level-Set

`surface_advancement_level_set` (develop.py:266) integriert pro Säule Σ dz/R(M) von oben nach unten. Es gibt **keine laterale Entwicklung**: kein Unterätzen, keine Flankenwinkel, kein Kantenrückzug aus dem Nachbargraben. Der Name und die Docstring-Formulierung „level-set-like … fast marching" sind irreführend; es ist ein 1D-Ray-Tracing pro Spalte. Bei Mack n = 18,2 (nahezu binäre Rate) ist der CD-Effekt vermutlich klein, aber unquantifiziert [VERDACHT]. Für die Tiefenauflösung ist der Ansatz konvergent (B3).

### B2 [BESTÄTIGT, klein] Keine vertikale Diffusion im PEB

`reaction_diffusion_analytical` blurrt (N,H,W) als N unabhängige 2D-Schichten: 20 nm lateral, 0 nm vertikal, in einem 50-nm-Film. Monkey-Test `audit_zdiff.py` (1D-Gauß entlang z, Neumann-Rand; Wirksamkeit verifiziert: Säure-Tiefenspanne 1,039× → 1,027×): CD-Änderung **0,00 nm** bei α = 1,06/µm und bei α = 8/µm (Dill-Sättigung flacht das Säureprofil auf 4 % ab). Formal inkonsistent, hier ohne messbare Folge; relevant für stark absorbierende Resists mit ungesättigter Belichtung.

### B3 [BESTÄTIGT, unkritisch] Film-Geometrie N·dz = Dicke + dz

`dz = thickness/(N−1)` (pipeline.py:1253), jede der N Schichten erhält Dicke dz → modellierter Film 52,5 nm bei N=21; „voll entwickelt" = 20 von 21 Schichten. Konvergenz (`audit_layers.py`, Dosis fest): CD 21,31 (N=6), 21,66 (11), 22,00 (21, 41, 81). Ab N=21 auf Pixelquantisierung konvergiert. Formaler Mangel, praktisch unkritisch.

### B4 [GELESEN] Optik-Pfad: skalar, Dünnmaske, ohne CRA-Schatten; zwei parallele, teils tote Implementierungen

- Genutzt wird `aerial/abbe.py::aerial_from_orders` + `_compute_tcc_matrix` (numerisches Quell-Pupillen-Überlappungsintegral, normiert) — skalar, keine Polarisation, keine Obliquität, kein 6°-Schatten im Thin-Mask-Pfad (die 6° gehen nur in die TMM-Reflektivität ein; `theta0` in pipeline.py:1554 hart 6,0 statt `constants.EUV_ANGLE_DEG`).
- `aerial/hopkins.py` (`compute_tcc`, SOCS) und `aerial/source.py` (parametrisierte Quellformen) werden von der Pipeline **nicht** benutzt (nur `opc/openilt_bridge.py` und `accel/chunked.py` nutzen `abbe_image`/`source.conventional`). Die Pipeline-Quellformen in `_compute_tcc_matrix` haben **hart codierte** Unterparameter: annular σ_in = 0,3σ, Dipol-Polradius 0,2σ, Polabstand 0,6σ, Quasar-Öffnung 30° — nicht in `SimulationConfig` exponiert, nicht mit `source.py` konsistent (dort Defaults 0,3/0,8, 0,2/0,6).
- Docstring `abbe.py` Kopf: „TCC(i,j) = 2·J₁(x)/x" — beschreibt nicht mehr die Implementierung (stale).
- `max_order`-Hartabschnitt in `aerial_from_orders` ist redundant zur TCC (harmlos).

### B5 [BESTÄTIGT] RCWA-TM: Li-Regel behauptet, Laurent-Regel implementiert

`rcwa_torch.py:178` berechnet `E_inv = Toeplitz(1/ε)` und benutzt es **nirgends** (grep: einzige Vorkommnis). TM-Eigenproblem Z. 188: `A = E − E·Kx·E⁻¹·Kx` — das ist Moharams ursprüngliche Formulierung (Laurent-Regel); Li's inverse Regel würde `inv(E_inv)` an Stelle von `E` verwenden. Docstring Z. 185 behauptet „Li's improved Fourier factorization". Monkey-Test `audit_numerics.py` (Ta-Gitter 22/44 nm, 60 nm, Vakuum-Substrat), relative Änderung der 0.-Ordnung von 41 → 81 Ordnungen: **TE 1,4·10⁻⁵, TM 7,2·10⁻³ — TM konvergiert 500× langsamer.** Betrifft `use_rcwa=True` (TE/TM-Mittel, pipeline.py:1730).

Weitere RCWA/Maske-Befunde [GELESEN]:
- `_build_ml_reflection_operator` Z. 503: beide Zweige der Bedingung liefern `n_layers[-1]` (letzte Si-Schicht) als Substrat — logisch falsch, numerisch gleich, da Substrat = Si.
- `geometry.py:196–201`: Mo/Si-n,k **hart codiert** (0,9238/0,00637; 0,999/0,00183) statt CXRO; `eps_sub` wird in der Pipeline entgegengenommen und **nie benutzt** (tot).
- `geometry.py:185`: Permittivität nur aus `absorber_layers[-1]`, Dicke aus *allen* Schichten summiert — bei `standard_euv_mask` (Ru-Cap in der Liste) wird die Cap-Dicke mit Ta-Permittivität gerechnet. Die Pipeline umgeht das (nur Ta), die öffentliche Funktion nicht.
- Taper/Undercut: `pipeline.py:1628` `pass` — Parameter werden akzeptiert und ignoriert (Mandat §12: ehrliche Kennzeichnung fehlt).
- `mo_si_stack` wird in `run_simulation` **ohne** `energy_eV` aufgerufen → ML-n,k immer bei 91,84 eV, Absorber bei `energy_eV(cfg.wavelength_nm)` — inkonsistent, sobald `wavelength_nm ≠ 13,5`.

---

## C. Numerik, toter Code, Einheiten, Magic Numbers

### C1 [BESTÄTIGT] ADI-PEB-Löser verletzt Massenerhaltung

`reaction_diffusion_adi` (peb.py:126): expliziter Halbschritt nutzt Spiegel-Neumann `lap[0] = 2(A₁−A₀)` (2. Ordnung), impliziter Halbschritt `(1+α)A₀ − αA₁` (Ghost = Rand, 1. Ordnung). Test (Zero-Flux, k=0, 10 Schritte): Masse **+0,14 %** (α=2,5), **+1,6 %** (α=10). Ein konsistentes Crank-Nicolson-Neumann-Schema erhält Masse auf Maschinengenauigkeit. **Nicht im Pipeline-Pfad** (dort nur der Gauß-Blur), aber exportierte API (`resist/__init__.py`) und Testgegenstand (`test_peb_laplacian.py`).

### C2 [GELESEN] Toter/defekter Zweig `surface_advancement_level_set(t_develop=None)`

develop.py:328–343: baut `profile_3d` zweimal auf und überschreibt es mit `(cum_time <= cum_time.max())` — das ist **überall 1**. Kein Aufrufer im Repo (grep), aber öffentliche Signatur.

### C3 [GELESEN] Tote Parameter und Legacy-Heuristiken
- `SimulationConfig.resist_threshold` (pipeline.py:144): definiert, **nie gelesen** (nur `resist_threshold_norm` wirkt).
- `SimulationConfig.mask_sidewall_roughness_nm`: von CLI gesetzt, **nie gelesen**.
- `poisson_shot_noise` ohne `dose`: `lam = acid·100` „heuristic scale factor" (stochastic.py:162) — Magic Number; die Funktion wird von `ler_lwr_estimate`/`rms_scaling_check` genutzt.
- `dose_to_acid` (exposure.py:443): Default `Q = 0,04` mit Begründung „lower Q to account for average depth absorption" — in der Pipeline nicht mehr genutzt, Docstring widerspricht `dill_Q`-Semantik.
- `_binomial_fallback`-Kommentar („several molecules per voxel") ist bei λ = 0,014 falsch; Normalnäherung wäre dort grob falsch (nur relevant ohne `torch.binomial`).

### C4 [GELESEN] Magic Numbers / Einheiten
- `nominal_dose = 20.0` zweimal hart (pipeline.py:1091, 1216).
- `RESIST_PRESETS` (5,0/2,5/3,0 nm SE-Blur) ohne Quelle.
- `peb.py`-Moduldocstring: k in „s⁻¹ M⁻¹" — tatsächlich wirkt k auf *relative* Konzentration, Einheit s⁻¹.
- `exposure.py`-Kopfformel „A(z) = A₀·exp[−(B + C·I)·z]" ist physikalisch unsinnig (mischt Absorption und Photorate); die Implementierung ist davon unberührt.
- `etch/bias.py:_CHEMISTRY_FORMULAS`: 35 Koeffizienten, „Coeffs fit to published data in JVST B, JECS, SPIE (1990–2010)" — **keine einzige konkrete Quelle**; `empirical_cd_bias`-Defaults „typical CF₄" ebenso; `apply_bias_to_aerial` σ = |bias|/(2·px) willkürlich. Nach Mandat: als „empirisch, nicht literaturbelegt" zu kennzeichnen.
- `source/plasma.py`: parametrisches Toy-Modell, nicht an die Pipeline angebunden; `_IN_BAND_SIGMA_EV`, `_LAMBERTIAN_NORM` ungenutzt; `dose_rate(losses=0.7)` willkürlich.

### C5 [GELESEN] CLI (`io/cli.py`)
- `process-window` Z. 398: **`el = (d_max − d_min)/target_cd·100`** — Exposure Latitude durch das CD in nm geteilt (Einheitenfehler; `metro/process_window.py:168` macht es richtig durch `best_dose`). Die CLI dupliziert die Logik statt `metro.process_window` zu rufen.
- `calibrate`: `pipeline_fn` fixiert Geometrie **64/32 nm, grid 128** (Z. 761–766) — eine FEM bei anderem Pitch wird stillschweigend gegen die falsche Geometrie gefittet. `dill_Q`-Bounds **(0,1; 2,0)** erlauben Q > 1 (Wahrscheinlichkeit). `peb_sigma_diff = 20` als Startwert hart (Pipeline-Default ist D-basiert).
- `simulate` exponiert weder `focus_nm`, `illumination_shape`, `exposure_stochasticity`, `development_stochasticity` noch `stochastic_ler_grid_y`.
- `metro/process_window.py::pw_metrics` liefert `dof_nm` in Fokus-*Indizes* und `el_pct` als Index-Anteil (Kommentar „dummy"), unter physikalischen Schlüsselnamen.

---

## D. Geprüft und korrekt befunden (mit Beleg)

| Gegenstand | Beleg |
|---|---|
| CXRO f1/f2 für Ta | Repo-CSV bei 91,34/92,39 eV identisch mit `henke.lbl.gov/optical_constants/sf/ta.nff` (abgerufen 2026-09-04): 9,60398/7,53869 und 9,51863/7,62518 |
| n,k Mo/Si/Ru bei 13,5 nm | 0,9234/0,0065; 0,9990/0,00183; 0,8867/0,0170 — <1 % gegen Referenz; δ,β-Formel r_e λ² N f/(2π) korrekt |
| Konstanten | CODATA 2018; HC_EV_NM = 1239,842; 1 mJ = 6,2415·10¹⁵ eV; 91,84 eV ↔ 13,5 nm |
| Photonenflussdichte | 6,80·10¹³ Photonen/cm² pro mJ/cm² (Standardwert) |
| Mack-Ratenmodell | R = R_max(a+1)(1−M)ⁿ/(a+(1−M)ⁿ)+R_min, a = (n+1)/(n−1)(1−M_th)ⁿ — Mack 1992 |
| Dill/Beer-Lambert | dose_z = D·e^{−(A+B)z}, z in µm, A,B in 1/µm konsistent |
| TMM | S-Matrix/Redheffer, Névot-Croce-Dämpfung, Im(k_z) ≥ 0 Zweigwahl — Standard (Macleod, Li 1996) |
| Defokus | φ_m = −π·f·m²·λ/P² konsistent mit W = f·NA²ρ²/2 |
| FFT-Blur vs. direkter Pfad | Statistik glatt über kernel=64-Schwelle (std 0,211 → 0,201); Mittel exakt erhalten |
| Poisson/Binomial-Sampling | Mittelwerte stochastisch = deterministisch (0,155–0,162 in allen Pfaden) |
| Schichtkonvergenz | CD konvergiert ab N=21 |
| Sub-Pixel-Kantenschätzer, n_eff, l_int | `test_ler_estimate.py` deckt Legacy-Äquivalenz, Seeds, NaN ab; Formeln Standard |
| Bragg-Periode ML | 6,9 nm vs. 6,79 nm Vakuumnäherung — konsistent (mo_si_stack-Kommentar) |
| LWR-Definition | `torch.std(unbiased=False)` = 1σ, dokumentiert |

---

## E. Was fehlt (nicht vorhanden, nicht nur falsch)

1. Eine belegte Diffusionslänge für den Validierungsmaßstab (22-nm-HP) — oder deren ehrliche Deklaration als Kalibrierparameter (A3).
2. Eine physikalisch konsistente Quencher-Behandlung in **beiden** Pfaden auf Diffusionsskala (A4).
3. Dokumentierte Dosis-Konvention und clear-field-Normierung (A2).
4. Absorbierte-Photonen-Statistik (A1), idealerweise schichtweise.
5. Vertikale Diffusion (B2) und laterale Entwicklung (B1).
6. Vektor-/CRA-Effekte im Thin-Mask-Pfad; Taper/Undercut real oder als „nicht implementiert" abgelehnt (B4/B5).
7. Tests für `io/cli.py` (7/8 Kommandos ungetestet, laut Übergabe), `io/rasterize.py`; ein Test, der A1 (Absorption) und A2 (Normierung) je als Invariante festhält.
8. Ein einheitliches `dx`/`dx_nm`-Signaturschema (13 vs. 6, laut Übergabe).

---

## F. Eigene Korrekturen in diesem Audit

- **Ta-Verdacht war falsch.** Ich hatte n=0,9426/k=0,0409 als Referenz erinnert; die Primärdatei bestätigt die Repo-Werte. Gedächtniswerte sind keine Referenz — der Abgleich gegen `ta.nff` war der richtige Schritt.
- **Q-Fix-Preflight P1** („Dosisfenster erfüllt") ist nach A2 zu revidieren: 10,5 mJ/cm² nominal = 6,8 mJ/cm² Wafer, unterhalb Vesters' Bereich.
- **Fortsetzung 10, Aussage „Photonenrauschen füllt das Budget fast aus"** war mit `absorption=1` gemessen und ist nach A1 nicht haltbar; die richtige Zahl ist 2,4 nm am Optimum (Zielband) und 10,3 nm am Default.
- v2-Scan-Spalte „CD_sto" war deterministisch (bereits in Fortsetzung 10 §5 vermerkt).

---

## G. Empfohlene Reihenfolge (Vorschlag — keine Umsetzung ohne Entscheidung)

1. **A2** Dosis-Konvention festlegen und dokumentieren (Entscheidung: clear-field-Normierung ja/nein). Alles andere wird sonst gegen die falsche Skala kalibriert.
2. **A1** `absorption = 1−e^{−(A+B)t}` durchreichen — mechanisch, belegt, Vorhersage geprüft.
3. **A5** Q-Fix — belegt; Bewertung nach 1.
4. **A4** Quencher auf Diffusionsskala, beide Pfade; k_Q·G₀ — Modellentscheidung, Plan vorlegen.
5. **A3** σ_diff als Kalibrierparameter deklarieren oder Quelle finden — nach 1–4 kalibrierbar.
6. **A6** `development_stochasticity` entweder physikalisch neu begründen oder als experimentell/deprecated kennzeichnen.
7. B5/C1/C5 (RCWA-TM, ADI, CLI-EL) — abgegrenzte mechanische Korrekturen.
8. C2–C4 Aufräumen toter Parameter, Magic Numbers, Docstrings.

---

## Anhang — Skripte und Rohdaten (Scratchpad, nicht im Repo)

`preflight_qfix.py`, `blur_diagnose.py`, `blur_diagnose_v2.py`, `left_flank.py`, `mechanism_check.py`, `edge_saturation.py`, `mean_mismatch.py` (Fortsetzung 10); `audit_layers.py`, `audit_zdiff.py`, `audit_absorption.py`, `audit_numerics.py` (dieser Bericht). Aerial-Normierung und CXRO-Abgleich als Inline-Skripte.

RCWA-Konvergenz (0.-Ordnung, TE/TM): M=11: 0,000221/0,000216; 21: 0,000221/0,000215; 41: 0,000221/0,000214; 81: 0,000221/0,000212; 121: 0,000221/0,000212.
