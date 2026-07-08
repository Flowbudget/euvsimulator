"""Test ML-integrated pipeline"""
import torch, sys
sys.path.insert(0, "src")

from euv.pipeline import run_simulation, SimulationConfig

cfg = SimulationConfig(na=0.33, sigma=0.8, period_nm=64, line_width_nm=32,
                       ml_n_bilayers=50, dose_mj_cm2=20, grid=256)
res = run_simulation(cfg)
img = res.aerial_image
center = img.shape[0] // 2
profile = img[center, :]
dx = 64.0 / img.shape[1]

print("=== 50 Bilayer ML, Conventional sigma=0.8 ===")
print(f"  Aerial: min={float(profile.min()):.4f}  max={float(profile.max()):.4f}")
print(f"  CD: {res.cd_nm:.1f} nm  NILS: {res.nils_value:.2f}")
print(f"  Abs.Refl: {res.absorber_reflectivity:.4f}")
print(f"  Resist: min={float(res.resist_profile.min()):.4f} max={float(res.resist_profile.max()):.4f}")
print()
print("  Aerial profile (center row, every 16th px):")
for i in range(0, img.shape[1], 16):
    x = (i - center) * dx
    print(f"    x={x:6.1f}nm  I={float(profile[i]):.4f}")

# Annular comparison
cfg_a = SimulationConfig(na=0.33, sigma=0.8, illumination_shape="annular",
                         period_nm=64, line_width_nm=32,
                         ml_n_bilayers=50, dose_mj_cm2=20, grid=256)
res_a = run_simulation(cfg_a)
profile_a = res_a.aerial_image[center, :]
print()
print("=== 50 Bilayer ML, Annular sigma=0.8 ===")
print(f"  Aerial: min={float(profile_a.min()):.4f}  max={float(profile_a.max()):.4f}")
print(f"  CD: {res_a.cd_nm:.1f} nm  NILS: {res_a.nils_value:.2f}")
print(f"  Abs.Refl: {res_a.absorber_reflectivity:.4f}")
print()
print("  Aerial profile:")
for i in range(0, img.shape[1], 16):
    x = (i - center) * dx
    print(f"    x={x:6.1f}nm  I={float(profile_a[i]):.4f}")

# Graded ML
cfg_g = SimulationConfig(na=0.33, sigma=0.8, period_nm=64, line_width_nm=32,
                         ml_n_bilayers=50, ml_grading_linear_nm=0.2,
                         ml_grading_parabolic_nm=0.1,
                         dose_mj_cm2=20, grid=256)
res_g = run_simulation(cfg_g)
print()
print("=== Graded ML (lin=0.2, para=0.1) ===")
print(f"  CD: {res_g.cd_nm:.1f} nm  NILS: {res_g.nils_value:.2f}")
print(f"  Abs.Refl: {res_g.absorber_reflectivity:.4f}")
