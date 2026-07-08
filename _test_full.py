"""Full pipeline test with correct axis analysis"""
import torch, sys
sys.path.insert(0, "src")
from euv.pipeline import run_simulation, SimulationConfig

cfg = SimulationConfig(na=0.33, sigma=0.8, period_nm=64, line_width_nm=32,
                       ml_n_bilayers=50, dose_mj_cm2=20, grid=128)
res = run_simulation(cfg)

img = res.aerial_image
G = img.shape[0]
dx = 64.0 / G

print(f"Aerial shape: {list(img.shape)}")
print(f"CD={res.cd_nm:.1f}nm  NILS={res.nils_value:.2f}  Abs.Refl={res.absorber_reflectivity:.4f}")

# Check ALL columns at center row — should show x-profile
center = G // 2
print(f"\nX-profile at center row (y=0, should vary with x):")
for i in range(0, G, 4):
    x = (i - center) * dx
    print(f"  x={x:6.1f}nm  I={float(img[center, i]):.4f}")

print(f"\nY-profile at center column (x=0, should be uniform):")
for r in range(0, G, 8):
    y = (r - center) * dx
    print(f"  y={y:6.1f}nm  I={float(img[r, center]):.4f}")

# Also print one complete row
print(f"\nFull row 0 (y=-32nm) — should be x-profile:")
for i in range(0, G, 4):
    x = (i - center) * dx
    print(f"  x={x:6.1f}nm  I={float(img[0, i]):.4f}")

print(f"\nResist profile at center row:")
center = res.resist_profile.shape[0] // 2
for i in range(0, res.resist_profile.shape[1], 4):
    x = (i - center) * dx
    print(f"  x={x:6.1f}nm  R={float(res.resist_profile[center, i]):.4f}")