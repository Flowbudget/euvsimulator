# OpEnUV – Session Context (2026-07-07)

## Project Name
- **Public:** OpEnUV (Open Source Extreme UV)
- **Internal/Code:** `euv`

## License & Philosophy
- **Apache-2.0** (Open Source)
- Open Core + Commercial Plugins (Support, Calibration, Training)
- Donations via GitHub Sponsors / Open Collective
- **Open Source ≠ Free:** Kernel is free, support + calibration cost money

## Goal
Open-source EUV lithography simulator from Sn plasma to CD metrology.
Primary: Education, research, chip startups.
Secondary: Small fabs without KLA/ASML budget.

## Technical Stack
- **Language:** Python (Core) + Rust (Performance – RCWA solver via PyO3)
- **GPU:** PyTorch CUDA
- **Limit:** RTX 5060 Ti (16 GB VRAM) – no production full-chip RCWA
- **Solution:** Hybrid approach: Rust for rigorous RCWA offline → CNN surrogate for runtime
- **Target Platform:** Debian 12/13

## Open Source Base (Licenses Verified ✅)
| Project | License | Usage |
|---------|---------|-------|
| ELitho | MIT | `multilayer.py` (TMM) direct adoption |
| TorchResist | Apache-2.0 | Resist simulation |
| OpenILT | MIT | Mask optimization (needs EUV port) |
| TorchLitho 2.0 | Apache-2.0 | GPU acceleration |
| OxiPhoton | Apache-2.0 | Rust TMM inspiration |
| gdstk | BSD-3 | GDSII I/O |
| KLayout | GPL-3.0 | GDS viewer (optional tool) |
| LithographySimulator | LGPL-2.1 | Keep as separate submodule |

**Key Insight:** ELitho has NO RCWA – only TMM+Fourier. The mask-3D solver must be built from scratch (6–8 months).

## Corrected Assumptions (from destructive review)
1. ❌ ELitho has RCWA → ✅ **No, only TMM+Fourier. Needs new development.**
2. ❌ MIT code from DE → legal to China → ✅ **Check EU Dual-Use/Wassenaar. Not generically legal.**
3. ❌ 16 GB VRAM sufficient → ✅ **Factor 1000 off. Only 5×5µm demo.**
4. ❌ Panoramic is niche player → ✅ **HyperLith v7 has TRIG, PanSEM, PanSO, ARMI.**
5. ❌ Data 80% public → ✅ **~65% public, 20% fittable, 15% trade secrets.**

## Roadmap

| Milestone | Description |
|-----------|-------------|
| Foundation | Project scaffold, constants, material database |
| Optics Core | TMM multilayer mirror optics |
| EM Simulation | RCWA 1D mask 3D solver (PyTorch) |
| Layout Import | GDSII I/O + dummy mask generation |
| Aerial Image | Abbe/Hopkins partially coherent imaging + pupil |
| End-to-End | First complete simulation pipeline 🎉 |
| Source Model | Plasma source model + dose calibration |
| Resist Core | TorchResist-based photoresist model |
| Stochastic Effects | Resist stochastics + LER/LWR |
| REST API | REST server + SDK |
| Production RCWA | Rust-based rigorous RCWA solver |
| 2D RCWA | Full 2D mask simulation |

## Key Decisions (Session 2026-07-07)
1. ✅ **Don't start with ELitho integration** – check BAFA first
2. ✅ **RCWA/Waveguide = Hybrid Rust + PyTorch CNN Surrogate**
3. ✅ **Open Source, Apache-2.0** (not AGPL)
4. ✅ **GitHub Sponsors + Open Collective for donations**
5. ✅ **CLI name: `euv`**
6. ✅ **Fallback: Opus 4.8 when DeepSeek stalls**

## Open Items
- [ ] BAFA inquiry: Does EUV sim fall under EU Dual-Use?
- [ ] Freedom-to-Operate patent analysis (ASML, KLA, Panoramic)
- [ ] First contacts to Chinese institutes + Fraunhofer
- [ ] Get Panoramic test license

## Files in This Project
| File | Description |
|------|-------------|
| `README.md` | Project overview |
| `2026-07-07-OPUS-plan.md` | Detailed phase plan (Opus 4.8) |
| `_docs/strategy.md` | Market analysis + architecture |
| `_docs/destructive-review.md` | Destructive review (corrections) |
| `_docs/research.md` | Technical research (components) |
| `session-context.md` | **This file** – complete session context |

---