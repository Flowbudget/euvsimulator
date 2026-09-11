"""Pattern search over the four campaign CSVs: power-law regressions, invariants,
closed-form checks of the chain, residual structure. No keywords, only numbers."""
import math, sys
import numpy as np, pandas as pd
from euvsimulator.pipeline import SimulationConfig
from euvsimulator.resist.develop import MackModel

D = sys.argv[1]
np.set_printoptions(precision=3, suppress=True)
pd.set_option("display.width", 200); pd.set_option("display.max_columns", 30)
cfg0 = SimulationConfig()
C = cfg0.dill_C


def powerlaw(df, y, xs, label):
    """log y = a0 + sum a_i log x_i; prints exponents and residual spread."""
    d = df.dropna(subset=[y] + xs)
    d = d[(d[y] > 0)]
    X = np.column_stack([np.ones(len(d))] + [np.log(d[x].astype(float)) for x in xs])
    b, *_ = np.linalg.lstsq(X, np.log(d[y].astype(float)), rcond=None)
    res = np.log(d[y].astype(float)) - X @ b
    print(f"  {label}: ln {y} = {b[0]:.3f} + " + " + ".join(f"{bi:.3f}·ln {x}" for bi, x in zip(b[1:], xs)) +
          f"   | residual sd {res.std():.3f} (≈ {100*res.std():.1f} %), n={len(d)}")
    return b, res, d


def t_eff(tau, t):
    return t if (tau is None or (isinstance(tau, float) and math.isnan(tau))) else tau * (1 - math.exp(-t / tau))


print("=" * 100); print("C1  optics x resist (full_chem defaults, 1:1 lines, target = pitch/2)")
c1 = pd.read_csv(f"{D}/c1.csv"); print("(table omitted, 32 rows)")
c1["E_edge"] = c1.d2s * c1.i_mean_norm      # local dose at the image mean (the 1:1 edge for a symmetric image)
c1["E_edge_max"] = c1.d2s * c1.i_max_norm
print("\n  Invariant test: local dose at the printed edge, E_edge = D2S · I_mean/I_clear")
print(c1.groupby(["na", "sigma", "shape"])["E_edge"].agg(["mean", "std"]).round(4).to_string())
print("  overall E_edge: mean %.4f  sd %.4f  (relative %.1f %%)" % (c1.E_edge.mean(), c1.E_edge.std(), 100 * c1.E_edge.std() / c1.E_edge.mean()))
print("  E_edge vs NILS correlation: %.3f ; vs k1: %.3f" % (c1.E_edge.corr(c1.nils), c1.E_edge.corr(c1.k1)))
powerlaw(c1, "d2s", ["i_mean_norm"], "D2S vs 1/I_mean")
c1["abs_slope"] = c1.slope.abs()
powerlaw(c1, "abs_slope", ["nils", "pitch"], "|CD slope| vs NILS, pitch")
c1["slope_theory"] = c1.pitch / (2 * math.pi) * 0  # placeholder
c1["slope_x_nils_over_pitch"] = c1.slope * c1.nils / c1.pitch
print("  slope·NILS/pitch:", c1.slope_x_nils_over_pitch.describe()[["mean", "std", "min", "max"]].round(4).to_dict())

print("\n" + "=" * 100); print("C2  PEB kinetics (T, bake time, D, law) at 64/32 nm")
c2 = pd.read_csv(f"{D}/c2.csv"); print("(table omitted, 90 rows)")
ana = c2[c2.law == "analytical"].copy()
ana["t_eff"] = [t_eff(tau, t) for tau, t in zip(ana.tau, ana.t_bake)]
ana["k_teff"] = ana.k * ana.t_eff
# closed form without diffusion: M_edge = exp(-k t_eff H_edge) = M*  ->  H_edge = -ln M* /(k t_eff)
# E_edge = D2S * I_mean_norm (I_mean_norm of this optics = 0.318-like, take from C1 default optics row)
sel = c1[np.isclose(c1.pitch, 64) & np.isclose(c1.na, 0.33) & np.isclose(c1.sigma, 0.8) & (c1["shape"] == "conventional")]
i_mean_default = float(sel.i_mean_norm.iloc[0])
ana["E_edge"] = ana.d2s * i_mean_default
ana["H_edge"] = 1 - np.exp(-C * ana.E_edge)
ana["ln_M_edge"] = -ana.k_teff * ana.H_edge      # predicted ln M at the edge in the no-diffusion limit
print("\n  analytical law: k·t_eff·H_edge (= −ln M at the printed edge if diffusion were absent):")
print(ana.groupby(["D", "t_bake"])["ln_M_edge"].agg(["mean", "std"]).round(4).to_string())
print("  by temperature:"); print(ana.groupby("T")["ln_M_edge"].agg(["mean", "std"]).round(4).to_string())
ana["blur"] = np.sqrt(2 * ana.D * ana.t_eff)
powerlaw(ana, "d2s", ["k_teff", "blur"], "D2S vs k·t_eff, blur")
powerlaw(ana, "d2s", ["k_teff"], "D2S vs k·t_eff only")
print("  correlation of residual structure: -ln M_edge vs blur: %.3f" % ana.ln_M_edge.corr(ana.blur))
rd = c2[c2.law == "reaction_diffusion"].copy()
print("\n  law ratio D2S(analytical)/D2S(reaction_diffusion):")
m = ana.merge(rd, on=["T", "t_bake", "D"], suffixes=("_a", "_r"))
m["ratio"] = m.d2s_a / m.d2s_r
print(m.pivot_table(index="T", columns="t_bake", values="ratio").round(3).to_string())
print("  ratio vs D:"); print(m.groupby("D")["ratio"].agg(["mean", "std"]).round(3).to_string())

print("\n" + "=" * 100); print("C3  development (random Mack parameters, develop time, thickness) at 64/32 nm, default PEB")
c3 = pd.read_csv(f"{D}/c3.csv")
# M* : inhibitor level where the Mack rate equals thickness / t_dev (front just reaches the substrate)
def m_star(row):
    mk = MackModel(R_max=row.R_max, R_min=row.R_min, M_th=row.M_th, n=row.n)
    target = row.thickness / row.t_dev
    lo, hi = 0.0, 1.0
    import torch
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if float(mk.rate(torch.tensor(mid, dtype=torch.float64))) > target: lo = mid
        else: hi = mid
    return 0.5 * (lo + hi)
c3["M_star"] = c3.apply(m_star, axis=1)
kte = cfg0.peb_k * t_eff(cfg0.peb_acid_lifetime_s, cfg0.peb_t_bake)
c3["E_edge"] = c3.d2s * i_mean_default
c3["H_edge"] = 1 - np.exp(-C * c3.E_edge)
c3["M_edge_pred"] = np.exp(-kte * c3.H_edge)     # inhibitor at the printed edge, no-diffusion limit
print(c3.round(4).to_string(index=False))
print("\n  Closed-form test: M at the printed edge (from D2S) vs M* (rate = thickness/t_dev):")
ok = c3.dropna(subset=["d2s"])
print("  corr(ln M_edge_pred, ln M*) = %.3f ; mean ratio M_edge/M* = %.3f, sd %.3f" % (
    np.corrcoef(np.log(ok.M_edge_pred), np.log(ok.M_star))[0, 1], (ok.M_edge_pred / ok.M_star).mean(), (ok.M_edge_pred / ok.M_star).std()))
powerlaw(ok, "d2s", ["n", "R_max", "M_th", "t_dev", "thickness"], "D2S vs Mack params (power law)")
ok = ok.assign(x=ok.thickness / (ok.R_max * ok.t_dev))
powerlaw(ok, "d2s", ["x", "n", "M_th"], "D2S vs thickness/(R_max t_dev), n, M_th")
print("  rows that never print:", c3.d2s.isna().sum(), "of", len(c3))

print("\n" + "=" * 100); print("C4  stochastic (blur, SE blur, dissolution cell, dose) at 64/32 nm, 512 rows, 2 seeds")
c4 = pd.read_csv(f"{D}/c4.csv"); print(c4.round(3).to_string(index=False))
ph = c4[c4.cell == 0]
powerlaw(ph, "ler", ["dose", "sigma_diff", "se_blur"], "photon-only LER vs dose, blur, SE blur")
powerlaw(ph, "l_int", ["sigma_diff", "se_blur"], "correlation length vs blur, SE blur")
print("  l_int / sqrt(sigma_diff^2 + se_blur^2):", (ph.l_int / np.sqrt(ph.sigma_diff**2 + ph.se_blur**2)).describe()[["mean", "std"]].round(3).to_dict())
for cell in (2.0, 4.3):
    cc = c4[c4.cell == cell].merge(ph, on=["sigma_diff", "se_blur", "dose_factor"], suffixes=("", "_ph"))
    cc["excess2"] = cc.ler**2 - cc.ler_ph**2
    print(f"  cell {cell} nm: LER² − LER²_photon (quadrature excess) by dose factor:",
          cc.groupby("dose_factor")["excess2"].agg(["mean", "std"]).round(3).to_dict("index"))
    print(f"           excess² vs blur:", cc.groupby("sigma_diff")["excess2"].mean().round(3).to_dict())
print("  n_eff · l_int / (512 rows · dx):", (c4.n_eff * c4.l_int / (512 * 64 / 64)).describe()[["mean", "std"]].round(3).to_dict())
print("  stochastic CD − deterministic CD:", (c4.cd_stoch - c4.cd_det).describe()[["mean", "std", "min", "max"]].round(3).to_dict())
