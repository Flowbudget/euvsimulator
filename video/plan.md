# OpEnUV Explainer Video — Plan

## Narrative Arc
"From Light to Nanostructure: How EUV Lithography Simulation Works"

The video explains how OpEnUV simulates the complete EUV lithography pipeline: source → mask → optics → aerial image → resist → metrology.

## Scenes

### Scene 1: Title
- Title: "OpEnUV - Open EUV Lithography Simulator"
- Subtitle: "From Plasma Source to CD Measurement"
- Dark background, neon tech palette
- Duration: 3s

### Scene 2: The EUV Light Source (Plasma)
- Show a tin droplet (circle) being hit by a laser pulse (arrow)
- Plasma forms, emits EUV photons at 13.5 nm
- Label: LPP (Laser-Produced Plasma) — CE ~5%
- Minimal math: λ = 13.5 nm

### Scene 3: Multilayer Mask
- Show mask cross-section: substrate → Mo/Si multilayer (40-50 pairs) → Ru cap → TaN absorber
- Animate EUV photons reflecting from multilayer (Bragg condition)
- Show absorber blocking (dark field) vs. reflecting (bright field)
- Label: Bragg mirror — R ≈ 70%

### Scene 4: Projection Optics
- Show 6 mirrors (low-NA) or 8-10 (high-NA) arrangement
- Animate light path through the optical column
- Demonstrate anamorphic 4×/8× for high-NA
- WFE budget: < 1 nm RMS

### Scene 5: Aerial Image Formation
- Show how the mask pattern is projected onto the wafer
- Hopkins/Abbe imaging theory visualization
- Dipole illumination diagram
- Aerial image intensity profile (edge slope = ILS/NILS)

### Scene 6: Resist & Stochastic Effects
- Show resist cross-section (CAR)
- Animate: photon → photoelectron → secondary electrons → acid generation
- Show diffusion blur
- Shot noise visualization (photon counting statistics)

### Scene 7: Development & CD Metrology
- Show developer removing deprotected resist
- Resulting resist profile
- CD measurement (top-down, cross-section)
- Process window (Bossung plot): DoF vs EL

### Scene 8: OpEnUV Architecture
- Module tree animation (source, mask3d, aerial, resist, metro...)
- CLI commands floating in
- "From GDS to CD in one command"
- GitHub URL

## Color Palette (Neon Tech)
- BG: #0A0A0A
- Primary: #00F5FF (cyan)
- Secondary: #FF00FF (magenta)
- Accent: #39FF14 (neon green)
- Tertiary: #FFD93D (yellow)
- MONO font

## Timing
Total target: ~60-90 seconds
Each scene: ~7-12 seconds
