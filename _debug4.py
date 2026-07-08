"""Final test — profile at space region (row 0), not absorber center"""
import torch, math, sys
sys.path.insert(0, "src")

from euv.materials import CXROTable
from euv.optics.multilayer import mo_si_stack
from euv.optics.tmm import reflectivity
from euv.aerial.pupil import pupil_grid
from euv.aerial.source import conventional
from euv.aerial.abbe import abbe_image

G = 256
period_m = 64e-9

table = CXROTable()
theta0 = torch.tensor(math.radians(6.0), dtype=torch.float64)
wl_t = torch.tensor([13.5e-9], dtype=torch.float64)
n_si, k_si = table.refractive_index("Si", 91.84)
n_sub = torch.tensor(complex(n_si, k_si), dtype=torch.complex128)

ml = mo_si_stack(n_bilayers=50)
_, r_sp = reflectivity(ml.n_layers, ml.thicknesses, wl_t, theta0, n_substrate=n_sub)
r_space = r_sp[0]
n_ta, k_ta = table.refractive_index("Ta", 91.84)
n_abs = torch.tensor(complex(n_ta, k_ta), dtype=torch.complex128)
d_abs = torch.tensor([60e-9])
full_n = torch.cat([n_abs.unsqueeze(0), ml.n_layers])
full_d = torch.cat([d_abs, ml.thicknesses])
_, r_ab = reflectivity(full_n, full_d, wl_t, theta0, n_substrate=n_sub)
r_absorber = r_ab[0]

mask_tx = torch.full((G,), r_space, dtype=torch.complex128)
for i in range(G):
    x_i = -period_m/2 + i * period_m / G
    if abs(x_i) <= 16e-9:
        mask_tx[i] = r_absorber

mask_2d = mask_tx.unsqueeze(1).expand(G, G).clone()
mask_fft = torch.fft.fftshift(torch.fft.fft2(mask_2d))

source = conventional(G, sigma=0.8)
fx, fy, inside = pupil_grid(G, na=0.33)
pupil = inside.to(torch.float64).to(torch.complex128)

aerial = abbe_image(mask_fft, source, fx, fy, pupil, na=0.33,
                    period_m=period_m, wavelength_m=13.5e-9)

# Profile at ROW 0 (space region, x=-32nm)
profile_row0 = aerial[0, :]  # All columns at y≈-32nm
center = G // 2
dx = period_m / G * 1e9

# Profile at CENTER ROW (absorber region, x=0nm)
profile_center = aerial[center, :]

print("=== Abbe Image ===")
print(f"  Row 0    (space region, y={(-period_m/2*1e9):.1f}nm):")
print(f"    min={float(profile_row0.min()):.4f}  max={float(profile_row0.max()):.4f}")
for i in range(0, G, 16):
    print(f"    col {i:3d}  I={float(profile_row0[i]):.4f}")

print(f"\n  Center row (absorber region, y=0nm):")
print(f"    min={float(profile_center.min()):.4f}  max={float(profile_center.max()):.4f}")
for i in range(0, G, 16):
    print(f"    col {i:3d}  I={float(profile_center[i]):.4f}")

# Show the full 2D image spatial structure
print(f"\n  Full 2D aerial (center 32×32 pixels):")
for r in range(center-16, center+16, 4):
    vals = " ".join(f"{float(aerial[r,c]):.3f}" for c in range(center-16, center+16, 4))
    y_pos = (r - center) * dx
    print(f"    y={y_pos:5.1f} | {vals}")