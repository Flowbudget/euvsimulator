"""Fix mask construction and test grid sizes"""
import torch, math, sys
sys.path.insert(0, "src")

from euv.materials import CXROTable
from euv.optics.multilayer import mo_si_stack
from euv.optics.tmm import reflectivity
from euv.aerial.pupil import pupil_grid
from euv.aerial.source import conventional
from euv.aerial.abbe import abbe_image

def run_ml_sim(G, period_nm=64, cd_nm=32):
    """cd_nm = line width (absorber)"""
    period_m = period_nm * 1e-9
    half_line = cd_nm / 2 * 1e-9  # 16nm for cd=32nm
    
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

    # Mask: absorber line centered, width = cd_nm
    mask_tx = torch.full((G,), r_space, dtype=torch.complex128)
    for i in range(G):
        x_i = -period_m/2 + i * period_m / G
        if abs(x_i) <= half_line:  # Only the absorber center
            mask_tx[i] = r_absorber

    mask_2d = mask_tx.unsqueeze(1).expand(G, G).clone()
    mask_fft = torch.fft.fftshift(torch.fft.fft2(mask_2d))

    source = conventional(G, sigma=0.8)
    fx, fy, inside = pupil_grid(G, na=0.33)
    pupil = inside.to(torch.float64).to(torch.complex128)
    
    df = 1.0 / (period_m * G)
    fc = 0.33 / 13.5e-9
    r_px = fc / df
    resolved = r_px < G/2
    print(f"G={G:4d}:  pupil_px={r_px:.0f}  half={G//2}  {'RESOLVED' if resolved else 'UNRESOLVED'}")
    
    aerial = abbe_image(mask_fft, source, fx, fy, pupil, na=0.33,
                        period_m=period_m, wavelength_m=13.5e-9)
    
    # Check the CENTER ROW (should go through the pattern)
    center = G // 2
    profile = aerial[center, :]
    dx = period_m / G * 1e9
    vals = [float(profile[i]) for i in range(0, G, max(1, G//16))]
    print(f"  Row center: min={float(profile.min()):.4f}  max={float(profile.max()):.4f}  mean={float(profile.mean()):.4f}")
    
    if resolved:
        prof_str = " | ".join(f"{v:.3f}" for v in vals[:16])
        print(f"  Profile: {prof_str}")
    
    # Also check a row at the edge
    profile_edge = aerial[0, :]
    print(f"  Row 0:      min={float(profile_edge.min()):.4f}  max={float(profile_edge.max()):.4f}")
    
    return aerial

for G in [64, 128, 256, 512, 1024]:
    run_ml_sim(G)
    print()