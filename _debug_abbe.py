"""Debug Abbe imaging — trace the exact computation for a single source point"""
import torch, math, sys
sys.path.insert(0, "src")

from euv.materials import CXROTable
from euv.optics.multilayer import mo_si_stack
from euv.optics.tmm import reflectivity
from euv.aerial.pupil import pupil_grid

# Setup
G = 256
period_m = 64e-9
wl_m = 13.5e-9
na = 0.33
half = G // 2

table = CXROTable()
theta0 = torch.tensor(math.radians(6.0), dtype=torch.float64)
wl_t = torch.tensor([wl_m], dtype=torch.float64)
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

print("r_space:", r_space, "|r|²:", float(abs(r_space)**2))
print("r_absorber:", r_absorber, "|r|²:", float(abs(r_absorber)**2))

# Build mask
x = torch.linspace(-period_m/2, period_m/2, G)
half_line = 16e-9
mask_tx = torch.full((G,), r_space, dtype=torch.complex128)
for i in range(G):
    if abs(x[i].item()) <= half_line:
        mask_tx[i] = r_absorber

mask_2d = mask_tx.unsqueeze(1).expand(G, G).clone()

# FFT + shift
mask_fft = torch.fft.fftshift(torch.fft.fft2(mask_2d))

# Step-by-step: reproduce what Abbe does for a SINGLE source point at center
# Check: ifft2(ifftshift(mask_fft)) gives back mask_2d?
recovered = torch.fft.ifft2(torch.fft.ifftshift(mask_fft))
max_err = float((recovered - mask_2d).abs().max())
print(f"FFT roundtrip error: {max_err:.2e}")
if max_err > 1e-10:
    print("  ERROR: FFT roundtrip is not exact!")
else:
    print("  OK: FFT roundtrip is exact")

# The coherent image is |mask_2d|²
intensity = (recovered * recovered.conj()).real
center = G // 2
print(f"\nCoherent image (center row, first 20 px):")
for i in range(0, 20):
    print(f"  px {i:3d}  x={x[i].item()*1e9:.1f}nm  I={float(intensity[center, i]):.6f}  |mask|²={float(abs(mask_2d[i, 0])**2):.6f}")

# Now the key question: what does the Abbe code actually do?
# It uses source-fx-fy from pupil_grid
fx, fy, inside = pupil_grid(G, na)
# And the source array

from euv.aerial.source import conventional
source = conventional(G, sigma=0.8)

# Let me directly run the Abbe code's inner loop
df = 1.0 / (period_m * G)
fc = na / wl_m
pupil_radius_px = fc / df

src_mask = source > 1e-6
src_indices = torch.nonzero(src_mask)
print(f"\nSource points: {src_indices.shape[0]}")
print(f"pupil_radius_px = {pupil_radius_px:.1f}")
print(f"half = {half}")
branch = "pupil covers grid" if pupil_radius_px >= half else "pupil resolved"
print(f"Branch: {branch}")

# For the first source point (likely center), trace manually
first_si = src_indices[0, 0].item() 
first_sj = src_indices[0, 1].item()
weight = source[first_si, first_sj].item()
sx = (first_si - half) / half
sy = (first_sj - half) / half
shift_x = int(round(sx * pupil_radius_px))
shift_y = int(round(sy * pupil_radius_px))

print(f"\nFirst source point: ({first_si}, {first_sj}) weight={weight:.4f}")
print(f"  sx={sx:.4f} sy={sy:.4f}")
print(f"  shift_x={shift_x} shift_y={shift_y}")

shifted = torch.roll(mask_fft, shifts=(-shift_x, -shift_y), dims=(0, 1))
x_start = half - int(round(pupil_radius_px))
x_end = half + int(round(pupil_radius_px)) + 1
y_start = half - int(round(pupil_radius_px))
y_end = half + int(round(pupil_radius_px)) + 1

# Clamp to grid boundaries
x_start = max(0, x_start)
x_end = min(G, x_end)
y_start = max(0, y_start)
y_end = min(G, y_end)

pupil = inside.to(torch.float64).to(torch.complex128)

if pupil_radius_px < half:
    pupil_sub = pupil[x_start:x_end, y_start:y_end]
    sub = shifted[x_start:x_end, y_start:y_end]
    filtered = sub * pupil_sub
    padded = torch.zeros_like(mask_fft)
    padded[x_start:x_end, y_start:y_end] = filtered
    coherent_img = torch.fft.ifft2(torch.fft.ifftshift(padded))
else:
    filtered = shifted * pupil
    coherent_img = torch.fft.ifft2(torch.fft.ifftshift(filtered))

coherent_intensity = (coherent_img * coherent_img.conj()).real
print(f"\nAbbe coherent image for this source (center row):")
for i in range(0, 20):
    print(f"  px {i:3d}  x={x[i].item()*1e9:.1f}nm  I={float(coherent_intensity[center, i]):.6f}")
print(f"  max={float(coherent_intensity.max()):.4f}  min={float(coherent_intensity.min()):.4f}")

# Also show around center
print(f"\n  Around center px:")
for i in range(center-5, center+6):
    print(f"  px {i:3d}  x={x[i].item()*1e9:.1f}nm  I={float(coherent_intensity[center, i]):.6f}")