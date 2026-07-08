"""Fix: the coherent image for EACH source is shifted. The SUM is what matters."""
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

# Use the Abbe function
source = conventional(G, sigma=0.8)
fx, fy, inside = pupil_grid(G, na=0.33)
pupil = inside.to(torch.float64).to(torch.complex128)

aerial = abbe_image(mask_fft, source, fx, fy, pupil, na=0.33, 
                    period_m=period_m, wavelength_m=13.5e-9)

center = G // 2
profile = aerial[center, :]
print("=== Abbe image (full, conventional σ=0.8) ===")
print(f"min={float(profile.min()):.4f}  max={float(profile.max()):.4f}  mean={float(profile.mean()):.4f}")
dx = period_m / G * 1e9
for i in range(0, G, 16):
    x_pos = (i - center) * dx
    print(f"  x={x_pos:6.1f}nm  I={float(profile[i]):.4f}")

# The Abbe image IS non-uniform now. The earlier test was wrong because
# it used the mask from the TMM section in the pipeline, which also works.
# Wait - but the pipeline test showed uniform output!

# Let me check: is the issue that the pipeline produces the mask correctly
# but the Abbe call in the pipeline has different parameters?
print()
print("=== Verification: direct coherent image (no source) ===")
coherent = torch.fft.ifft2(torch.fft.ifftshift(mask_fft))
direct_int = (coherent * coherent.conj()).real
dp = direct_int[center, :]
print(f"min={float(dp.min()):.4f}  max={float(dp.max()):.4f}")
for i in range(0, G, 16):
    x_pos = (i - center) * dx
    print(f"  x={x_pos:6.1f}nm  I={float(dp[i]):.4f}")