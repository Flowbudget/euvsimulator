"""Quick grid test — only small grids"""
import torch, math, sys
sys.path.insert(0, "src")

from euv.materials import CXROTable
from euv.optics.multilayer import mo_si_stack
from euv.optics.tmm import reflectivity
from euv.aerial.pupil import pupil_grid
from euv.aerial.source import conventional
from euv.aerial.abbe import abbe_image

period_m = 64e-9
wl_m = 13.5e-9
na = 0.33

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
print(f"r_space={abs(r_space)**2:.4f}  r_absorber={abs(r_absorber)**2:.4f}")

for G in [64, 128]:
    mask_tx = torch.full((G,), r_space, dtype=torch.complex128)
    for i in range(G):
        x_i = -period_m/2 + i * period_m / G
        if abs(x_i) <= 16e-9:
            mask_tx[i] = r_absorber

    mask_2d = mask_tx.unsqueeze(1).expand(G, G).clone()
    mask_fft = torch.fft.fftshift(torch.fft.fft2(mask_2d))
    
    source = conventional(G, sigma=0.8)
    fx, fy, inside = pupil_grid(G, na)
    pupil = inside.to(torch.float64).to(torch.complex128)
    
    # Check pupil resolution
    df = 1.0 / (period_m * G)
    fc = na / wl_m
    r_px = fc / df
    print(f"G={G}: pupil_radius_px={r_px:.0f} half={G//2} resolved={r_px < G/2}")
    
    aerial = abbe_image(mask_fft, source, fx, fy, pupil, na=na,
                        period_m=period_m, wavelength_m=wl_m)
    
    # Check the X-profile at center row
    center = G // 2
    dx = period_m / G * 1e9
    vals_x = []
    for i in range(G):
        x_pos = (i - center) * dx
        vals_x.append((x_pos, float(aerial[center, i])))
    
    print(f"  Center row: min={min(v for _,v in vals_x):.4f} max={max(v for _,v in vals_x):.4f}")
    unique_vals = len(set(f"{v:.4f}" for _,v in vals_x))
    print(f"  Unique intensity values in row: {unique_vals} (1=uniform)")
    
    if unique_vals > 1:
        print(f"  X-profile (first 16):")
        for x_pos, v in vals_x[:16]:
            print(f"    x={x_pos:6.1f}nm  I={v:.4f}")
    print()