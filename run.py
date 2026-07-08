=== Minimales Config-YAML als Vorlage ===
# simulate.yml – OpEnUV Konfiguration
period_nm: 64.0          # Linien/Raum-Periode [nm]
line_width_nm: 32.0      # Linienbreite [nm] (CD target)
dose_mj_cm2: 20.0        # Dosis [mJ/cm²]
na: 0.33                 # Numerische Apertur (0.33 Low-NA, 0.55 High-NA)
sigma: 0.8               # Partielle Kohärenz (0.2-0.9)
orders: 21               # RCWA Fourier-Ordnungen
absorber: Ta             # Absorber-Material
resist_threshold: 0.5    # Entwicklungs-Schwellwert
grid_size: 256           # Simulations-Gitter [px]
focus_nm: 0.0            # Defokus [nm]
output_dir: results/      # Ausgabe-Verzeichnis

=== Beispiel: Simulation mit Config ===
# Config speichern:
euv simulate --config simulate.yml

# Oder direkt per CLI:
euv simulate --period 64 --cd 32 --dose 22 --na 0.55

=== Workflow ===
1) euv make-mask --period 64 --cd 32            # Maske erzeugen
2) euv simulate --config simulate.yml            # Simulieren
3) Parameter anpassen und wiederholen

=== Python API ===
$ cat
