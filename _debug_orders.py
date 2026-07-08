"""Debug aerial_from_orders"""
import torch, math, sys
sys.path.insert(0, "src")

from euv.aerial.abbe import aerial_from_orders

# Simulate simple orders
a = -0.0804 - 0.0800j  # r_absorber
b = 0.5603 + 0.5771j   # r_space
duty = 0.5  # 32nm/64nm

# Fourier coefficients
c0 = a * duty + b * (1 - duty)
c1 = (a - b) * math.sin(math.pi * 1 * duty) / (math.pi * 1)
cm1 = (a - b) * math.sin(math.pi * (-1) * duty) / (math.pi * (-1))

print(f"c0  = {c0}  |c0|² = {abs(c0)**2:.4f}")
print(f"c1  = {c1}  |c1|² = {abs(c1)**2:.4f}")
print(f"c-1 = {cm1} |c-1|² = {abs(cm1)**2:.4f}")
print(f"c1 == c-1? {torch.allclose(torch.tensor(c1), torch.tensor(cm1))}")

# Run aerial_from_orders
amps = torch.tensor([cm1, c0, c1], dtype=torch.complex128)
orders = torch.tensor([-1, 0, 1], dtype=torch.int64)

aerial = aerial_from_orders(amps, orders, period_m=64e-9, na=0.33, 
                            wavelength_m=13.5e-9, sigma=0.8, grid=64)

G = 64
center = G // 2
profile = aerial[center, :]
print(f"\naerial_from_orders output:")
print(f"  min={float(profile.min()):.4f}  max={float(profile.max()):.4f}")

for i in range(G):
    x = (i - center) * 64.0 / G
    print(f"  x={x:6.1f}nm  I={float(profile[i]):.6f}")

# Manual check: I(x) for 3 orders
print(f"\nManual calculation:")
x_vals = torch.linspace(-32e-9, 32e-9, G)
for i in range(0, G, 8):
    x = x_vals[i]
    I = 0.0
    for mi, ri in [(-1, cm1), (0, c0), (1, c1)]:
        for mj, rj in [(-1, cm1), (0, c0), (1, c1)]:
            if abs(mi) > 1 or abs(mj) > 1: continue
            dm = abs(mi - mj)
            if dm > 0.8 * 0.33 * 64e-9 / 13.5e-9: continue  # coherence = 1.25
            phase = 2 * math.pi * (mi - mj) * x / 64e-9
            I += (ri * rj.conj() * math.e**(1j*phase)).real
    print(f"  x={(i - center)*64.0/G:6.1f}nm  I={I:.6f}")