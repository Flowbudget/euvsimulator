"""Pinpoint the coherent image bug"""
import torch, math, sys
sys.path.insert(0, "src")

from euv.materials import CXROTable
from euv.optics.multilayer import mo_si_stack
from euv.optics.tmm import reflectivity

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

G = 256
period_m = 64e-9
mask_tx = torch.full((G,), r_space, dtype=torch.complex128)
for i in range(G):
    x_i = -period_m/2 + i * period_m / G
    if abs(x_i) <= 16e-9:
        mask_tx[i] = r_absorber

mask_2d = mask_tx.unsqueeze(1).expand(G, G).clone()
print(f"mask_2d shape: {list(mask_2d.shape)}")
print(f"mask_2d[0,0] = {mask_2d[0,0]}")
print(f"|mask_2d[0,0]|² = {float(abs(mask_2d[0,0])**2)}")

mask_fft = torch.fft.fftshift(torch.fft.fft2(mask_2d))
recovered = torch.fft.ifft2(torch.fft.ifftshift(mask_fft))
print(f"recovered[0,0] = {recovered[0,0]}")
print(f"|recovered[0,0]|² = {float(abs(recovered[0,0])**2)}")
print(f"match: {torch.allclose(mask_2d, recovered)}")

# Manual element-wise
i = (recovered * recovered.conj()).real
print(f"intensity[0,0] = {float(i[0,0])}")
print(f"intensity[half,0] = half={G//2}  val={float(i[G//2, 0])}")

# Now the problem: the intensity is computed from ifft2 but it seems wrong
# Let's also check the FIRST source point from Abbe
from euv.aerial.source import conventional
source = conventional(G, sigma=0.8)
src_mask = source > 1e-6
src_indices = torch.nonzero(src_mask)
print(f"\nSource points: {src_indices.shape[0]}")

# Find a source point with non-zero weight
for idx in range(src_indices.shape[0]):
    si, sj = src_indices[idx, 0].item(), src_indices[idx, 1].item()
    w = source[si, sj].item()
    if w > 1e-6:
        print(f"First valid source: ({int(si)}, {int(sj)}) weight={w:.6f}")
        break

# Now replicate the Abbe else branch
from euv.aerial.pupil import pupil_grid
fx, fy, inside = pupil_grid(G, na=0.33)
pupil = inside.to(torch.float64).to(torch.complex128)

df = 1.0 / (period_m * G)
fc = 0.33 / 13.5e-9
pupil_radius_px = fc / df

sx = (si - G//2) / (G//2)
sy = (sj - G//2) / (G//2)
shift_x = int(round(sx * pupil_radius_px))
shift_y = int(round(sy * pupil_radius_px))

shifted = torch.roll(mask_fft, shifts=(-shift_x, -shift_y), dims=(0, 1))
filtered = shifted * pupil  # pupil covers all → filtered = shifted

coherent = torch.fft.ifft2(torch.fft.ifftshift(filtered))
intensity2 = (coherent * coherent.conj()).real
print(f"\nAfter Abbe loop (else branch):")
print(f"coherent[0,0] = {coherent[0,0]}")
print(f"intensity2[0,0] = {float(intensity2[0,0])}")

print(f"\nCenter row, first 6 pixels of intensity2:")
for i in range(6):
    print(f"  px {i}: I={float(intensity2[G//2, i]):.6f}  |mask_2d|²={float(abs(mask_2d[i, 0])**2):.6f}")