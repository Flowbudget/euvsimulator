"""Four exploratory campaigns over the validated parts of the chain (grid 64).
Writes one CSV per campaign; every row = one configuration with its outputs."""
import csv, dataclasses, itertools, math, random, sys, time
import numpy as np
from euvsimulator.pipeline import SimulationConfig, run_simulation

OUT = sys.argv[1]
T0 = time.time()
def log(msg): print(f"[{time.time()-T0:6.0f} s] {msg}", flush=True)

def sim(cfg):
    r = run_simulation(cfg)
    return r

def d2s(base, target, lo=0.05, hi=60.0, n=11):
    """Dose at which the full_chem CD equals target (bisection); NaN if never prints/clears."""
    if sim(dataclasses.replace(base, dose_mj_cm2=hi)).cd_nm > target: return float("nan")
    if sim(dataclasses.replace(base, dose_mj_cm2=lo)).cd_nm < target: return float("nan")
    for _ in range(n):
        m = math.sqrt(lo*hi)
        if sim(dataclasses.replace(base, dose_mj_cm2=m)).cd_nm > target: lo = m
        else: hi = m
    return math.sqrt(lo*hi)

def edge_metrics(base, dose, target):
    """CD slope dCD/dlnE around dose, NILS and normalised edge intensity at dose."""
    r = sim(dataclasses.replace(base, dose_mj_cm2=dose))
    rp = sim(dataclasses.replace(base, dose_mj_cm2=dose*1.05))
    rm = sim(dataclasses.replace(base, dose_mj_cm2=dose/1.05))
    slope = (rp.cd_nm - rm.cd_nm) / (2*math.log(1.05))
    a = r.aerial_image[r.aerial_image.shape[0]//2]
    amax, amean = float(a.max()), float(a.mean())
    return r, slope, amax, amean

# ---------------- C1: optics x resist ----------------
def c1():
    rows = []
    for pitch, na, sigma, shape in itertools.product((32.0, 44.0, 64.0, 90.0), (0.33, 0.55), (0.5, 0.8), ("conventional", "annular")):
        target = pitch/2
        base = SimulationConfig(grid=64, resist_model="full_chem", period_nm=pitch, line_width_nm=target, na=na, sigma=sigma, illumination_shape=shape)
        D = d2s(base, target)
        row = dict(pitch=pitch, na=na, sigma=sigma, shape=shape, k1=pitch/2*na/13.5, d2s=D)
        if D == D:
            r, slope, amax, amean = edge_metrics(base, D, target)
            row.update(nils=r.nils_value, cd=r.cd_nm, slope=slope, i_max_norm=amax/D, i_mean_norm=amean/D, refl=r.absorber_reflectivity)
        rows.append(row); log(f"C1 {row}")
    return rows

# ---------------- C2: PEB kinetics ----------------
def c2():
    rows = []
    for T, tb, Dd, law in itertools.product((80.0, 95.0, 110.0, 125.0, 140.0), (30.0, 60.0, 120.0), (2.0, 4.2, 8.0), ("analytical", "reaction_diffusion")):
        base = SimulationConfig(grid=64, resist_model="full_chem", peb_temperature_c=T, peb_t_bake=tb, peb_D=Dd, peb_model=law)
        D = d2s(base, 32.0)
        row = dict(T=T, t_bake=tb, D=Dd, law=law, k=base.peb_k, tau=base.peb_acid_lifetime_s if law=="analytical" else float("nan"),
                   k_trap=base.peb_k_trap_per_s if law=="reaction_diffusion" else float("nan"), d2s=D)
        if D == D:
            r, slope, amax, amean = edge_metrics(base, D, 32.0)
            row.update(nils=r.nils_value, cd=r.cd_nm, slope=slope)
        rows.append(row); log(f"C2 {row}")
    return rows

# ---------------- C3: development (Latin-hypercube sample) ----------------
def c3():
    rng = random.Random(7); rows = []
    for i in range(80):
        n = math.exp(rng.uniform(math.log(4), math.log(30)))
        rmax = math.exp(rng.uniform(math.log(15), math.log(250)))
        rmin = rmax*math.exp(rng.uniform(math.log(1e-4), math.log(2e-2)))
        mth = rng.uniform(0.25, 0.6)
        tdev = math.exp(rng.uniform(math.log(8), math.log(120)))
        th = rng.choice((30.0, 50.0, 80.0))
        base = SimulationConfig(grid=64, resist_model="full_chem", mack_n=n, mack_R_max=rmax, mack_R_min=rmin, mack_M_th=mth, develop_time_s=tdev, resist_thickness_nm=th)
        D = d2s(base, 32.0)
        row = dict(n=n, R_max=rmax, R_min=rmin, M_th=mth, t_dev=tdev, thickness=th, d2s=D)
        if D == D:
            r, slope, amax, amean = edge_metrics(base, D, 32.0)
            row.update(nils=r.nils_value, cd=r.cd_nm, slope=slope)
        rows.append(row); log(f"C3 {i} {row}")
    return rows

# ---------------- C4: stochastic (small) ----------------
def c4():
    rows = []
    base0 = SimulationConfig(grid=64, resist_model="full_chem")
    D0 = d2s(base0, 32.0)
    for sig, se, cell, dosef in itertools.product((4.0, 8.0, 12.0), (1.5, 2.5, 4.0), (0.0, 2.0, 4.3), (1.0, 1.5)):
        vals = []
        for seed in (1, 2):
            cfg = dataclasses.replace(base0, dose_mj_cm2=D0*dosef, peb_sigma_diff=sig, se_blur_nm=se, enable_stochastic=True,
                                      stochastic_ler_grid_y=512, stochastic_seed=seed,
                                      development_stochasticity=cell > 0, dissolution_cell_nm=cell if cell > 0 else 4.3)
            r = sim(cfg); m = r.ler_metadata or {}
            vals.append((r.ler_nm, r.lwr_nm, m.get("n_eff", float("nan")), m.get("l_int_nm", float("nan")), m.get("stochastic_cd_nm", float("nan")), r.cd_nm))
        v = np.nanmean(np.array(vals, dtype=float), axis=0)
        row = dict(sigma_diff=sig, se_blur=se, cell=cell, dose=D0*dosef, dose_factor=dosef, ler=v[0], lwr=v[1], n_eff=v[2], l_int=v[3], cd_stoch=v[4], cd_det=v[5])
        rows.append(row); log(f"C4 {row}")
    return rows

for name, fn in (("c1", c1), ("c2", c2), ("c3", c3), ("c4", c4)):
    rows = fn()
    keys = sorted({k for r in rows for k in r})
    with open(f"{OUT}/{name}.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys); w.writeheader(); w.writerows(rows)
    log(f"=== {name} done: {len(rows)} rows ===")
