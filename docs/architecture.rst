Architecture
============

Data flow
---------

::

  [GDSII / OASIS file]
       │  gdstk (io/gds.py)
       ▼
  [MaskGeometry: polygons + layers]
       │  rasterize (io/rasterize.py)
       ▼
  [Permittivity grid ε]  ←── [HenkeDB: n,k @13.5nm (materials/)]
       │
       ├──► [TMM Multilayer (optics/)] ──► [Mo/Si substrate R(θ,λ)]
       │
       ▼
  [RCWA mask3D solver]
       │  (rcwa_torch.py — 1D FMM + S-matrix)
       ▼
  [Diffraction orders: complex amplitudes]
       │
       ▼
  [Source model (source/)] ── in-band 13.5 nm + OoB
       │  → illumination source points
       ▼
  [Aerial Image (aerial/)]  ←── [Pupil: NA, aberrations, defocus]
       │  Abbe source-point summation
       ▼
  [Aerial intensity I(x,y)]
       │
       ├──► [CD / NILS metrology (metro/)]
       │
       ▼
  [Resist exposure (resist/)] ── SE blur, Dill kinetics
       ▼
  [PEB diffusion (resist/)]
       ▼
  [Development (resist/)] + [Stochastic LER/LWR (resist/)]
       ▼
  [Resist contour]  ── [Etch bias (etch/)]
       │
       ├──► [Process window (metro/)]
       ├──► [SEM render (metro/)]
       └──► [GDSII export (io/)]

Feedback loop (OPC/ILT):  Mask → RCWA → Aerial → Resist → CD → (adjust mask)

Module design
-------------

Each module lives under ``src/euv/`` and follows these conventions:

- Pure functions where possible, PyTorch tensors for GPU support
- Dataclass configs with sensible defaults
- Comprehensive docstrings (NumPy style)
- Tests in ``tests/test_<module>.py``
