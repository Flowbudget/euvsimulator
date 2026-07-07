Overview
========

OpEnUV simulates EUV lithography from mask to resist profile.  The pipeline
connects:

1. **Material database** — CXRO/Henke refractive indices for 92 elements
2. **Mask mask3D** — Rigorous coupled-wave analysis (RCWA) or thin-mask approximation
3. **Multilayer optics** — TMM for Mo/Si Bragg mirror reflectivity
4. **Projection pupil** — NA 0.33 (Low-NA) or 0.55 (High-NA), Zernike aberrations
5. **Aerial image** — Abbe source-point summation (coherent modes / TCC)
6. **Resist** — Deterministic exposure + PEB + development, stochastic LER/LWR
7. **Metrology** — CD extraction, Bossung process window, SEM rendering
8. **Etch bias** — Empirical CD bias correction

Architecture
------------

::

  src/euv/
  ├── constants/      Physical constants
  ├── materials/      CXRO material database
  ├── optics/         TMM multilayer reflectivity
  ├── mask3d/         RCWA 1D Fourier Modal Method
  ├── aerial/         Abbe imaging + pupil + source
  ├── source/         LPP tin-plasma model
  ├── resist/         Exposure + PEB + development + stochastics
  ├── io/             GDSII layout + CLI
  ├── metro/          CD metrology + process window
  ├── accel/          GPU acceleration layer
  ├── etch/           Etch bias model
  ├── calibrate/      Wafer calibration
  ├── api/            FastAPI REST API
  └── pipeline.py     End-to-end simulation
