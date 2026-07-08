"""Direct debug of aerial_from_orders"""
import torch, math, sys
sys.path.insert(0, "src")

# Manually compute
period_m = 64e-9
na, wavelength_m, sigma = 0.33, 13.5e-9, 0.8
G = 64
device = "cpu"

a = -0.0804 - 0.0800j
b = 0.5603 + 0.5771j
duty = 0.5

c0 = a * duty + b * (1 - duty)
c1 = (a - b) * math.sin(math.pi * 1 * duty) / (math.pi * 1)

# Replicate what the function does
x = torch.linspace(-period_m/2, period_m/2, G, device=device)
max_order = int(math.floor(na * period_m / wavelength_m))
coherence_orders = sigma * na * period_m / wavelength_m

print(f"max_order = {max_order}")
print(f"coherence_orders = {coherence_orders:.4f}")

amps = torch.tensor([c0, c1, c1], dtype=torch.complex128)  # m=-1, 0, 1
orders = torch.tensor([0, 1, -1], dtype=torch.int64)
M = 3

aerial_1d = torch.zeros(G, dtype=torch.complex128, device=device)

for i in range(M):
    mi = int(orders[i])
    ri = amps[i]
    if abs(ri) < 1e-15: continue
    if abs(mi) > max_order: continue
    
    for j in range(M):
        mj = int(orders[j])
        rj = amps[j]
        if abs(rj) < 1e-15: continue
        if abs(mj) > max_order: continue
        
        dm = abs(mi - mj)
        if dm > coherence_orders and dm > 0: continue  # only filter non-zero
        
        phase = 2.0 * math.pi * float(mi - mj) * x / period_m
        interference = ri * rj.conj() * torch.exp(1j * phase)
        aerial_1d += interference
        
        if float(aerial_1d[0].real) != 0:
            print(f"  ({mi},{mj}): phase factor adding {float(interference[0].real):.4f}+{float(interference[0].imag):.4f}j → sum={float(aerial_1d[0].real):.4f}")

aerial = aerial_1d.real.clamp(min=0.0).unsqueeze(1).expand(G, G).clone()

print(f"\nResult: min={float(aerial.min()):.4f} max={float(aerial.max()):.4f}")
profile = aerial[G//2, :]
for i in range(G):
    xi = (i - G//2) * 64.0 / G
    print(f"  x={xi:6.1f} I={float(profile[i]):.6f}")