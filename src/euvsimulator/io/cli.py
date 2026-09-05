"""CLI entry point for euvsimulator (`euv` command).

Usage:
    euv simulate [--config=FILE | --period=64 --cd=32 ...]
    euv make-mask --pitch=64 --cd=32 [--out=mask.gds]
    euv serve [--host=0.0.0.0 --port=8000]
    euv process-window --period=64 --cd=32 [--doses=... --focuses=...]
    euv materials [list | nk Si --energy=91.84]
    euv version
    euv bench
    euv info
    euv calibrate data.csv [--bootstrap=50]
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from euvsimulator.materials import DATA_DIR

app = typer.Typer(
    name="euv",
    help="euvsimulator — Open Source EUV Lithography Simulator",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


# ── version ────────────────────────────────────────────────────────────────


@app.command()
def version():
    """Print the installed version."""
    from euvsimulator import __version__

    print(f"euvsimulator v{__version__}")


# ── info ───────────────────────────────────────────────────────────────────


@app.command()
def info():
    """Print system information and configuration overview."""
    import torch

    from euvsimulator import __version__

    print(f"euvsimulator v{__version__}")
    print(f"PyTorch: {torch.__version__}")
    print(f"Device:  {'cuda' if torch.cuda.is_available() else 'cpu'}")
    if torch.cuda.is_available():
        for i in range(torch.cuda.device_count()):
            print(f"  GPU {i}: {torch.cuda.get_device_name(i)}")
    print()
    print("Modules:")
    print("  • constants/  — Physical constants")
    print("  • materials/  — CXRO material database")
    print("  • optics/     — TMM multilayer reflectivity")
    print("  • mask3d/     — RCWA Fourier modal method")
    print("  • aerial/     — Hopkins/TCC aerial imaging (abbe.py::aerial_from_orders);")
    print("                  pupil.py/source.py exist but are not wired into run_simulation()")
    print("  • source/     — LPP tin-plasma model")
    print("  • resist/     — Exposure, PEB, development, stochastics")
    print("  • io/         — GDSII layout I/O, rasterization")
    print("  • api/        — FastAPI REST server")
    print("  • pipeline/   — End-to-end simulation pipeline")
    print("  • metro/      — CD metrology + process window")
    print("  • accel/      — GPU acceleration layer")
    print("  • etch/       — Etch bias model")
    print("  • calibrate/  — Wafer calibration pipeline")
    print()
    print("Tests:     run `pytest tests/` (dev/test extra) for the current pass/fail count —")
    print("           not tracked here to avoid a stale hardcoded number (see CHANGELOG.md")
    print("           and docs/claude_code_arbeitslog.md for known issues)")
    print("License:   Apache-2.0")


# ── simulate ───────────────────────────────────────────────────────────────


@app.command()
def simulate(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="YAML/JSON config file path"),
    period: float = typer.Option(64.0, "--period", "-p", help="Pattern period [nm]"),
    cd: float = typer.Option(32.0, "--cd", help="Line width [nm]"),
    dose: float = typer.Option(20.0, "--dose", "-d", help="Exposure dose [mJ/cm²]"),
    na: float = typer.Option(0.33, "--na", help="Numerical aperture"),
    sigma: float = typer.Option(0.8, "--sigma", "-s", help="Partial coherence factor"),
    grid: int = typer.Option(256, "--grid", "-g", help="Grid size"),
    device: str = typer.Option("auto", "--device", help="PyTorch device: 'auto', 'cpu', or 'cuda'"),
    orders: int = typer.Option(21, "--orders", "-o", help="RCWA Fourier orders"),
    material: str = typer.Option("Ta", "--material", "-m", help="Absorber material"),
    threshold: float = typer.Option(0.5, "--threshold", "-t", help="Resist threshold"),
    se_blur: float = typer.Option(
        0.0, "--se-blur", help="Secondary-electron blur sigma [nm]; 0 = ideal, 5-10 realistic CAR"
    ),
    resist_preset: Optional[str] = typer.Option(
        None, "--resist-preset", help="Resist preset: CAR (5nm), nonCAR (2.5nm), HighNA (3nm)"
    ),
    resist_model: str = typer.Option(
        "aerial_threshold", "--resist-model", help="Resist model: aerial_threshold or full_chem"
    ),
    # Dill ABC exposure options -- defaults match SimulationConfig in pipeline.py:
    # Yamamoto et al. 2011, EUV-native, self-consistent with the Mack
    # development parameters below (see pipeline.py dill_A/B comment).
    dill_A: float = typer.Option(
        0.0,
        "--dill-A",
        help=(
            "Bleachable absorption coefficient [1/µm]; EUV CAR literature (Yamamoto et al. 2011, "
            "Fallica et al. 2016) suggests << dill-B"
        ),
    ),
    dill_B: float = typer.Option(
        4.44,
        "--dill-B",
        help=(
            "Non-bleachable absorption coefficient [1/µm]; default computed from the PHS/35 % "
            "tBOC composition at 1.20 g/cm3 via CXRO f2 (pipeline.py dill_B note); measured "
            "EUV CARs: 4.3-5.2 (Sekiguchi 2011, Fallica 2016)"
        ),
    ),
    dill_C: float = typer.Option(
        0.0152,
        "--dill-C",
        help=(
            "Photo-rate constant [cm²/mJ] for acid = G0*(1-exp(-C*E)), E incident; default = "
            "LBNL base-titration value for MET-2D (OSTI 1004159 Table 3); direct EUV-CAR "
            "measurements span 0.010-0.05 (Fallica 2017, LBNL); includes the PAG quantum "
            "efficiency, no separate Q factor"
        ),
    ),
    # PEB options
    peb_D: float = typer.Option(
        4.2,
        "--peb-D",
        help=(
            "Acid diffusivity [nm²/s]; diffusion length sqrt(2*D*t_eff) with t_eff the acid's "
            "effective lifetime, unless --peb-sigma-diff overrides it; default 4.2 = Kang 2010 "
            "(PHS-co-tBA, 90 C)"
        ),
    ),
    peb_k: float = typer.Option(
        7.87,
        "--peb-k",
        help=(
            "Deprotection rate constant [s⁻¹] at the PEB temperature, per unit relative acid; "
            "default = Yamamoto et al. 2011 Fig. 3/4 rate k*H = 0.166 s⁻¹ at 1.4 mJ/cm² divided "
            "by the acid fraction that --dill-C gives there (see pipeline.py peb_k note)"
        ),
    ),
    peb_acid_lifetime: Optional[float] = typer.Option(
        10.5,
        "--peb-acid-lifetime",
        help=(
            "Average acid lifetime [s] during PEB (first-order acid loss, Yamamoto 2011 Eq. 1); "
            "0 disables the loss"
        ),
    ),
    peb_t_bake: float = typer.Option(60.0, "--peb-t-bake", help="Bake time [s]"),
    peb_sigma_diff: Optional[float] = typer.Option(
        None,
        "--peb-sigma-diff",
        help="Analytical diffusion sigma [nm]; overrides --peb-D/--peb-t-bake when set",
    ),
    # Depth-resolved exposure/development options (2026-09-03)
    resist_thickness_nm: float = typer.Option(
        50.0,
        "--resist-thickness",
        help="Resist film thickness [nm]; Yamamoto et al. 2011's own better-resolved PROLITH case",
    ),
    develop_time_s: float = typer.Option(
        30.0,
        "--develop-time",
        help=(
            "Development time [s]; Yamamoto et al. 2011's own dissolution-rate measurement "
            "condition"
        ),
    ),
    n_develop_layers: int = typer.Option(
        21,
        "--n-develop-layers",
        help=(
            "Number of depth layers for the resolved exposure/PEB/development chain (numerical "
            "resolution, not physical)"
        ),
    ),
    development_model: str = typer.Option(
        "eikonal",
        "--development-model",
        help=(
            "Development front: 'eikonal' (isotropic front, lateral dissolution; physical) or "
            "'column' (vertical time-of-flight approximation)"
        ),
    ),
    # Stochastic / Shot Noise options
    enable_stochastic: bool = typer.Option(
        False, "--stochastic", help="Enable photon shot noise and LER/LWR extraction"
    ),
    stochastic_n_realisations: int = typer.Option(
        1, "--stochastic-realisations", help="Number of independent noise realisations"
    ),
    stochastic_seed: Optional[int] = typer.Option(
        None, "--stochastic-seed", help="RNG seed for reproducibility"
    ),
    # Mask-3D / RCWA options (Phase 4)
    use_rcwa: bool = typer.Option(
        False, "--use-rcwa", help="Use full RCWA instead of thin-mask analytic model"
    ),
    absorber_taper_deg: float = typer.Option(
        90.0, "--absorber-taper", help="Absorber sidewall angle from horizontal (90 = vertical)"
    ),
    mask_undercut_nm: float = typer.Option(
        0.0, "--mask-undercut", help="Absorber undercut at ML interface [nm]"
    ),
    # Mack development options -- defaults match SimulationConfig in pipeline.py;
    # see that file's mack_R_max comment for full sourcing (EUV-native,
    # self-consistent: Yamamoto et al. 2011, Rmax/Rmin/Mth/n all from one
    # real EUV-exposed resist, fit jointly with dill_A/B/C above).
    mack_R_max: float = typer.Option(68.6, "--mack-R-max", help="Max development rate [nm/s]"),
    mack_R_min: float = typer.Option(0.10, "--mack-R-min", help="Min development rate [nm/s]"),
    mack_n: float = typer.Option(18.2, "--mack-n", help="Dissolution selectivity (contrast)"),
    mack_M_th: float = typer.Option(
        0.39, "--mack-M-th", help="Threshold inhibitor concentration [0-1]"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", help="Output directory (prints to stdout if omitted)"
    ),
):
    """Run a full end-to-end simulation.

    Reads from a YAML/JSON config file, or uses command-line parameters.
    """
    from euvsimulator.pipeline import RESIST_PRESETS, SimulationConfig, run_simulation

    if config is not None:
        cfg_path = Path(config)
        if cfg_path.suffix in (".yaml", ".yml"):
            import yaml

            raw = yaml.safe_load(cfg_path.read_text())
        elif cfg_path.suffix == ".json":
            raw = json.loads(cfg_path.read_text())
        else:
            typer.echo(f"Unsupported config format: {cfg_path.suffix}", err=True)
            raise typer.Exit(1)
        cfg = SimulationConfig(**raw)
    else:
        # Apply resist preset if given
        se_blur_nm = se_blur
        if resist_preset is not None:
            if resist_preset not in RESIST_PRESETS:
                typer.echo(
                    "Unknown resist preset: "
                    f"{resist_preset}. Available: {list(RESIST_PRESETS.keys())}",
                    err=True,
                )
                raise typer.Exit(1)
            se_blur_nm = RESIST_PRESETS[resist_preset]

        cfg = SimulationConfig(
            period_nm=period,
            line_width_nm=cd,
            dose_mj_cm2=dose,
            na=na,
            sigma=sigma,
            grid=grid,
            device=device,
            n_rcwa_orders=orders,
            absorber_material=material,
            resist_threshold_norm=threshold,
            se_blur_nm=se_blur_nm,
            resist_model=resist_model,
            # Dill ABC exposure parameters
            dill_A=dill_A,
            dill_B=dill_B,
            dill_C=dill_C,
            # PEB parameters
            peb_D=peb_D,
            peb_k=peb_k,
            peb_t_bake=peb_t_bake,
            peb_sigma_diff=peb_sigma_diff,
            peb_acid_lifetime_s=(peb_acid_lifetime if peb_acid_lifetime else None),
            # Mack development parameters
            mack_R_max=mack_R_max,
            mack_R_min=mack_R_min,
            mack_n=mack_n,
            mack_M_th=mack_M_th,
            # Depth-resolved exposure/development parameters
            resist_thickness_nm=resist_thickness_nm,
            develop_time_s=develop_time_s,
            n_develop_layers=n_develop_layers,
            development_model=development_model,
            # Stochastic / Shot Noise parameters
            enable_stochastic=enable_stochastic,
            stochastic_n_realisations=stochastic_n_realisations,
            stochastic_seed=stochastic_seed,
            # Mask-3D / RCWA parameters (Phase 4)
            use_rcwa=use_rcwa,
            absorber_taper_deg=absorber_taper_deg,
            mask_undercut_nm=mask_undercut_nm,
        )

    typer.echo("[>] Running EUV lithography simulation...")
    result = run_simulation(cfg)

    out = {
        "cd_nm": float(f"{result.cd_nm:.2f}"),
        "nils": float(f"{result.nils_value:.4f}"),
        "absorber_reflectivity": float(f"{result.absorber_reflectivity:.4f}"),
        "aerial_max": float(f"{result.aerial_image.max():.4f}"),
        "aerial_shape": list(result.aerial_image.shape),
        "ler_nm": float(f"{result.ler_nm:.4f}"),
        "lwr_nm": float(f"{result.lwr_nm:.4f}"),
        "config": {
            "period_nm": cfg.period_nm,
            "line_width_nm": cfg.line_width_nm,
            "dose_mj_cm2": cfg.dose_mj_cm2,
            "na": cfg.na,
            "sigma": cfg.sigma,
        },
    }

    if output:
        out_dir = Path(output)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "result.json").write_text(json.dumps(out, indent=2))
        # Save aerial image as numpy for plotting
        import numpy as np

        np.save(out_dir / "aerial_image.npy", result.aerial_image.cpu().numpy())
        np.save(out_dir / "resist_profile.npy", result.resist_profile.cpu().numpy())

        # Generate a simple PNG of the aerial image
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
            im1 = ax1.imshow(result.aerial_image.cpu().numpy(), cmap="hot", aspect="equal")
            ax1.set_title("Aerial Image")
            plt.colorbar(im1, ax=ax1)
            im2 = ax2.imshow(result.resist_profile.cpu().numpy(), cmap="gray", aspect="equal")
            ax2.set_title("Resist Profile")
            plt.colorbar(im2, ax=ax2)
            plt.tight_layout()
            plt.savefig(str(out_dir / "simulation.png"), dpi=150)
            plt.close()
            typer.echo(f"\U0001f4c1 Results saved to {out_dir.resolve()}")
        except Exception:
            typer.echo(f"\U0001f4c1 Results saved to {out_dir.resolve()} (PNG skipped)")
    else:
        print(json.dumps(out, indent=2))


# ── make-mask ──────────────────────────────────────────────────────────────


@app.command(name="make-mask")
def make_mask(
    pitch: float = typer.Option(64.0, "--pitch", help="Pattern pitch [nm]"),
    cd: float = typer.Option(32.0, "--cd", help="Line width [nm]"),
    n_lines: int = typer.Option(20, "--n-lines", help="Number of lines"),
    height: float = typer.Option(2000.0, "--height", help="Line height [nm]"),
    out: str = typer.Option("mask.gds", "--out", "-o", help="Output GDSII file"),
):
    """Generate a line/space test mask as GDSII."""
    import gdstk

    lib = gdstk.Library(unit=1e-9, precision=1e-12)
    cell = lib.new_cell("LS")
    for i in range(n_lines):
        x0 = i * pitch
        rect = gdstk.rectangle((x0, 0), (x0 + cd, height), layer=0)
        cell.add(rect)
    lib.write_gds(out)
    typer.echo(f"✅ Wrote {out} — {n_lines} lines at {pitch:.0f} nm pitch, {cd:.0f} nm CD")


# ── process-window ─────────────────────────────────────────────────────────


@app.command(name="process-window")
def process_window(
    period: float = typer.Option(64.0, "--period", help="Pattern period [nm]"),
    cd: float = typer.Option(32.0, "--cd", help="Line width [nm]"),
    dose_start: float = typer.Option(10.0, "--dose-start", help="Start dose [mJ/cm²]"),
    dose_end: float = typer.Option(40.0, "--dose-end", help="End dose [mJ/cm²]"),
    dose_steps: int = typer.Option(7, "--dose-steps", help="Number of dose values"),
    focus_start: float = typer.Option(-50.0, "--focus-start", help="Start focus [nm]"),
    focus_end: float = typer.Option(50.0, "--focus-end", help="End focus [nm]"),
    focus_steps: int = typer.Option(7, "--focus-steps", help="Number of focus values"),
    output: Optional[str] = typer.Option(None, "--output", help="Output JSON file path"),
    output_plot: Optional[str] = typer.Option(
        None, "--output-plot", help="Output heatmap PNG file path"
    ),
    output_csv: Optional[str] = typer.Option(None, "--output-csv", help="Output CSV file path"),
    tolerance: float = typer.Option(
        0.1, "--tolerance", help="CD tolerance fraction (e.g., 0.1 = ±10%)"
    ),
    na: float = typer.Option(0.33, "--na", help="Numerical aperture"),
    sigma: float = typer.Option(0.8, "--sigma", help="Partial coherence factor"),
    grid: int = typer.Option(256, "--grid", help="Grid size"),
    se_blur: float = typer.Option(0.0, "--se-blur", help="Secondary-electron blur sigma [nm]"),
    resist_model: str = typer.Option("aerial_threshold", "--resist-model", help="Resist model"),
):
    """Compute a process window (Bossung plot) over dose × focus.

    Runs multiple simulations across a dose-focus grid and extracts
    depth of focus (DoF) and exposure latitude (EL).
    """
    import numpy as np

    from euvsimulator.pipeline import SimulationConfig, run_simulation

    doses = np.linspace(dose_start, dose_end, dose_steps)
    focuses = np.linspace(focus_start, focus_end, focus_steps)
    target_cd = cd

    typer.echo(f"\U0001f4ca Computing process window: {dose_steps}×{focus_steps} grid...")
    cd_matrix = np.zeros((dose_steps, focus_steps))
    nils_matrix = np.zeros((dose_steps, focus_steps))

    for i, d in enumerate(doses):
        for j, f in enumerate(focuses):
            cfg = SimulationConfig(
                period_nm=period,
                line_width_nm=cd,
                dose_mj_cm2=d,
                focus_nm=f,
                grid=grid,
                na=na,
                sigma=sigma,
                se_blur_nm=se_blur,
                resist_model=resist_model,
            )
            result = run_simulation(cfg)
            cd_matrix[i, j] = result.cd_nm
            nils_matrix[i, j] = result.nils_value
            typer.echo(
                f"  dose={d:.1f}, focus={f:.0f} → "
                f"CD={result.cd_nm:.2f} nm, NILS={result.nils_value:.3f}"
            )

    # Process-window metrics from the library routine (single definition).
    # The previous inline copy divided the exposure latitude by the target
    # CD in nm instead of by the dose (unit error, fixed 2026-09-04); EL is
    # (dose_max - dose_min)/dose_best x 100 % at best focus, DoF the in-spec
    # focus range at best dose. metro.process_window expects (N_focus, N_dose).
    from euvsimulator.metro.process_window import process_window as _pw

    lo = target_cd * (1 - tolerance)
    hi = target_cd * (1 + tolerance)
    pw = _pw(cd_matrix.T, list(doses), list(focuses), target_cd=target_cd, tolerance=tolerance)
    dof = pw["dof_nm"]
    el = pw["el_pct"]

    # Print ASCII Bossung table
    print()
    print("Bossung Table (CD in nm):")
    header = "focus\\dose | " + " ".join(f"{d:7.1f}" for d in doses)
    print(header)
    print("-" * len(header))
    for j in range(focus_steps):
        row = f"{focuses[j]:+7.0f}    | " + " ".join(
            f"{cd_matrix[i, j]:7.2f}" for i in range(dose_steps)
        )
        print(row)

    print()
    print(f"Target CD:     {target_cd:.1f} nm")
    print(f"Tolerance:     ±{tolerance * 100:.0f}% (±{target_cd * tolerance:.1f} nm)")
    print(f"Depth of Focus: {dof:.1f} nm")
    print(f"Exposure Latitude: {el:.1f}%")

    result = {
        "target_cd_nm": float(target_cd),
        "doses": doses.tolist(),
        "focuses": focuses.tolist(),
        "cd_matrix": cd_matrix.tolist(),
        "nils_matrix": nils_matrix.tolist(),
        "depth_of_focus_nm": float(dof),
        "exposure_latitude_pct": float(el),
        "tolerance": tolerance,
    }

    if output:
        Path(output).write_text(json.dumps(result, indent=2))
        typer.echo(f"\U0001f4c1 Results saved to {output}")

    # Generate heatmap plot
    if output_plot:
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

            # CD heatmap
            im1 = ax1.imshow(
                cd_matrix.T,
                origin="lower",
                aspect="auto",
                extent=[dose_start, dose_end, focus_start, focus_end],
                cmap="RdYlGn",
                vmin=lo,
                vmax=hi,
            )
            ax1.set_xlabel("Dose [mJ/cm²]")
            ax1.set_ylabel("Focus [nm]")
            ax1.set_title(f"CD Heatmap (target={target_cd:.0f} nm, tol=±{tolerance * 100:.0f}%)")
            plt.colorbar(im1, ax=ax1, label="CD [nm]")
            # Contour lines at spec limits
            ax1.contour(
                doses,
                focuses,
                cd_matrix.T,
                levels=[lo, hi],
                colors="k",
                linewidths=1,
                linestyles="--",
            )

            # NILS heatmap
            im2 = ax2.imshow(
                nils_matrix.T,
                origin="lower",
                aspect="auto",
                extent=[dose_start, dose_end, focus_start, focus_end],
                cmap="viridis",
            )
            ax2.set_xlabel("Dose [mJ/cm²]")
            ax2.set_ylabel("Focus [nm]")
            ax2.set_title("NILS Heatmap")
            plt.colorbar(im2, ax=ax2, label="NILS")

            plt.tight_layout()
            plt.savefig(output_plot, dpi=150)
            plt.close()
            typer.echo(f"\U0001f4ca Heatmap saved to {output_plot}")
        except Exception as e:
            typer.echo(f"⚠️  Plot generation failed: {e}", err=True)

    # Export CSV
    if output_csv:
        import csv

        with open(output_csv, "w", newline="") as f:
            writer = csv.writer(f)
            # Header row
            writer.writerow([""] + [f"{d:.1f}" for d in doses])
            # Data rows
            for j, f in enumerate(focuses):
                row = [f"{f:.0f}"] + [f"{cd_matrix[i, j]:.2f}" for i in range(dose_steps)]
                writer.writerow(row)
        typer.echo(f"\U0001f4c4 CSV saved to {output_csv}")


# ── materials ──────────────────────────────────────────────────────────────


@app.command()
def materials(
    element: Optional[str] = typer.Argument(None, help="Element symbol (e.g. Si, Mo, Ta)"),
    energy: float = typer.Option(
        91.84,
        "--energy",
        "-e",
        help=(
            "Photon energy [eV]. Default is 91.84 eV (corresponding to 13.5 nm wavelength via E ="
            " hc/λ)."
        ),
    ),
):
    """Query the CXRO material database.

    Without arguments: lists all available elements.
    With an element: prints refractive index at the given energy.
    """
    from euvsimulator.materials import CXROTable

    table = CXROTable()

    if element is None:
        # List available elements by scanning the data directory
        d = Path(DATA_DIR)
        if d.exists():
            available = sorted(f.stem for f in d.iterdir() if f.suffix.lower() == ".csv")
        else:
            available = []
        print(f"Available materials ({len(available)}):")
        for el in available:
            print(f"  • {el}")
    else:
        # Get refractive index
        try:
            n, k = table.refractive_index(element, energy)
            delta = 1 - n
            from euvsimulator.constants import HC_EV_NM

            wavelength_nm = HC_EV_NM / energy
            print(f"Material:      {element}")
            print(f"Energy:        {energy:.2f} eV")
            print(f"Wavelength:    {wavelength_nm:.4f} nm")
            print(f"n (refractive): {n:.6f}")
            print(f"k (extinction): {k:.6f}")
            print(f"delta (1-n):   {delta:.6f}")
            print(f"eps_real:      {n * n - k * k:.6f}")
            print(f"eps_imag:      {2 * n * k:.6f}")
        except ValueError as e:
            typer.echo(f"❌ {e}", err=True)
            raise typer.Exit(1)


# ── serve ──────────────────────────────────────────────────────────────────


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", help="Bind address"),
    port: int = typer.Option(8000, "--port", "-p", help="Listen port"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Auto-reload on changes"),
):
    """Start the REST API server."""
    import uvicorn

    typer.echo(f"\U0001f680 Starting euvsimulator API server on http://{host}:{port}")
    typer.echo(f"   Docs: http://{host}:{port}/docs")
    uvicorn.run(
        "euvsimulator.api.main:app",
        host=host,
        port=port,
        log_level="info",
        reload=reload,
    )


# ── bench ──────────────────────────────────────────────────────────────────


@app.command()
def bench():
    """Run a quick performance benchmark."""
    import time

    import torch

    from euvsimulator.pipeline import SimulationConfig, run_simulation

    typer.echo("⏱️  Running benchmark...")

    configs = {
        "small (256×256, 21 orders)": SimulationConfig(
            period_nm=64.0,
            line_width_nm=32.0,
            grid=256,
            n_rcwa_orders=21,
        ),
        "medium (512×512, 31 orders)": SimulationConfig(
            period_nm=64.0,
            line_width_nm=32.0,
            grid=512,
            n_rcwa_orders=31,
        ),
    }

    for label, cfg in configs.items():
        t0 = time.perf_counter()
        result = run_simulation(cfg)
        elapsed = time.perf_counter() - t0
        device = "cpu"
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        print(f"  {label}:")
        print(f"    Wall time:  {elapsed:.3f} s")
        print(f"    CD:         {result.cd_nm:.2f} nm")
        print(f"    NILS:       {result.nils_value:.4f}")
        print(f"    Aerial max: {result.aerial_image.max():.4f}")

    # VRAM estimate
    from euvsimulator.accel.vram_budget import vram_report

    try:
        print(f"\nVRAM Estimates:\n{vram_report()}")
    except ImportError:
        print("\n(accel module not yet available)")


# ── calibrate ───────────────────────────────────────────────────────────────


@app.command(name="calibrate")
def calibrate(
    data_file: str = typer.Argument(..., help="Path to wafer CD data (CSV or JSON)"),
    initial_params_file: Optional[str] = typer.Option(
        None, "--initial-params", "-i", help="YAML/JSON file with initial parameter guesses"
    ),
    bounds_file: Optional[str] = typer.Option(
        None, "--bounds", "-b", help="YAML/JSON file with parameter bounds"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output JSON file for results"
    ),
    bootstrap_samples: int = typer.Option(
        50, "--bootstrap", help="Number of bootstrap samples for confidence intervals"
    ),
    method: str = typer.Option("Nelder-Mead", "--method", help="SciPy minimisation method"),
    maxiter: int = typer.Option(500, "--maxiter", help="Maximum iterations for optimiser"),
    seed: Optional[int] = typer.Option(None, "--seed", help="Random seed for bootstrap"),
    period: float = typer.Option(
        64.0, "--period", help="Pattern period of the measured FEM [nm] (wafer scale)"
    ),
    cd: float = typer.Option(32.0, "--cd", help="Nominal line width of the measured FEM [nm]"),
    grid: int = typer.Option(128, "--grid", help="Simulation grid for the fit"),
    se_blur: float = typer.Option(
        5.0, "--se-blur", help="Secondary-electron blur sigma [nm] held fixed during the fit"
    ),
):
    """Calibrate resist-model parameters to measured wafer CD data.

    The simulated geometry (--period/--cd) MUST match the measured pattern:
    until 2026-09-04 it was hard-wired to 64/32 nm regardless of the data.

    The input data file must be CSV (dose,focus,cd columns) or JSON with
    WaferCDData format. See `euv.calibrate.wafer_fit.WaferCDData` for details.

    Fits the resist model parameters (Dill C, PEB k/t_bake/sigma_diff, Mack
    R_max/R_min/n/M_th) to minimise RMSE between simulated and measured CD across
    the focus-exposure matrix. Restrict the fitted set with an initial-parameter
    file: an 8-parameter fit against a small FEM is under-determined.
    """
    import json
    from pathlib import Path

    import numpy as np

    from euvsimulator.calibrate.wafer_fit import WaferCDData, bootstrap_fit, fit_resist_params
    from euvsimulator.pipeline import SimulationConfig, run_simulation

    # Load wafer data
    data_path = Path(data_file)
    if data_path.suffix.lower() == ".csv":
        # CSV format: dose,focus,cd_nm
        import csv

        doses = []
        foci = []
        cd_values = []
        with open(data_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                doses.append(float(row["dose"]))
                foci.append(float(row["focus"]))
                cd_values.append(float(row["cd_nm"]))
        # Reconstruct matrix (assumes regular grid)
        dose_vals = sorted(set(doses))
        focus_vals = sorted(set(foci))
        cd_matrix = np.zeros((len(dose_vals), len(focus_vals)))
        dose_to_idx = {d: i for i, d in enumerate(dose_vals)}
        focus_to_idx = {f: i for i, f in enumerate(focus_vals)}
        # NB: do not name the loop variable `cd` -- it would shadow the --cd
        # option and silently feed the last measured CD into the simulated
        # line width (found 2026-09-05 by the synthetic-FEM smoke test).
        for d, f, cd_meas in zip(doses, foci, cd_values):
            cd_matrix[dose_to_idx[d], focus_to_idx[f]] = cd_meas
        data = WaferCDData(
            dose_values=np.array(dose_vals),
            focus_values=np.array(focus_vals),
            cd_matrix_nm=cd_matrix,
        )
    elif data_path.suffix.lower() in (".json", ".yaml", ".yml"):
        import yaml

        raw = (
            yaml.safe_load(data_path.read_text())
            if data_path.suffix.lower() in (".yaml", ".yml")
            else json.loads(data_path.read_text())
        )
        data = WaferCDData(**raw)
    else:
        typer.echo(f"Unsupported format: {data_path.suffix}", err=True)
        raise typer.Exit(1)

    typer.echo(
        f"\U0001f4ca Loaded wafer data: {data.n_dose}×{data.n_focus} FEM "
        f"({data.cd_matrix_nm.shape[0]}×{data.cd_matrix_nm.shape[1]})"
    )
    typer.echo(f"   Dose range: {data.dose_values.min():.1f}–{data.dose_values.max():.1f} mJ/cm²")
    typer.echo(f"   Focus range: {data.focus_values.min():.1f}–{data.focus_values.max():.1f} nm")

    # Load initial parameters
    if initial_params_file:
        import yaml

        ip_path = Path(initial_params_file)
        initial_params = (
            yaml.safe_load(ip_path.read_text())
            if ip_path.suffix.lower() in (".yaml", ".yml")
            else json.loads(ip_path.read_text())
        )
    else:
        # Default initial guess for typical EUV CAR resist
        initial_params = {
            "dill_C": 0.0152,  # LBNL MET-2D, direct measurement (see pipeline.py dill_C comment)
            "peb_k": 7.87,  # Yamamoto 2011 Fig. 3/4 rate / acid fraction (see pipeline.py peb_k)
            "peb_t_bake": 60.0,
            # Anderson et al. 2009 (OSTI 961531): measured EUV deprotection blur, "Reference"
            # formulations cluster 17-35nm
            "peb_sigma_diff": 20.0,
            # Yamamoto et al. 2011, EUV-native, self-consistent with dill_C above (see pipeline.py
            # mack_R_max comment)
            "mack_R_max": 68.6,
            # Yamamoto et al. 2011, EUV-native, self-consistent with dill_C above (see pipeline.py
            # mack_R_min comment)
            "mack_R_min": 0.10,
            # Yamamoto et al. 2011, EUV-native, self-consistent with dill_C above (see pipeline.py
            # mack_n comment)
            "mack_n": 18.2,
            # Yamamoto et al. 2011, EUV-native, self-consistent with dill_C above (see pipeline.py
            # mack_M_th comment)
            "mack_M_th": 0.39,
        }

    # Load bounds
    if bounds_file:
        import yaml

        b_path = Path(bounds_file)
        bounds = (
            yaml.safe_load(b_path.read_text())
            if b_path.suffix.lower() in (".yaml", ".yml")
            else json.loads(b_path.read_text())
        )
    else:
        bounds = {
            "dill_C": (0.01, 0.2),
            "peb_k": (0.05, 2.0),
            "peb_t_bake": (30.0, 120.0),
            "peb_sigma_diff": (
                1.0,
                40.0,
                # widened: Anderson et al. 2009 (OSTI 961531) measured real EUV resists up to
                # 38.4 nm -- a 20 nm cap would have artificially excluded valid fits
            ),
            "mack_R_max": (10.0, 500.0),
            "mack_R_min": (0.01, 10.0),
            "mack_n": (
                1.5,
                30.0,
                # widened: Schnattinger PhD thesis (FAU, 193nm CAR resist, see pipeline.py mack_n
                # comment) measured n=25.14 -- a 20 cap would have excluded that real (if
                # wavelength-caveated) value
            ),
            "mack_M_th": (0.1, 0.9),
        }

    # Create pipeline function
    _defaults = SimulationConfig()

    def pipeline_fn(dose: float, focus: float, **params) -> float:
        cfg = SimulationConfig(
            period_nm=period,
            line_width_nm=cd,
            dose_mj_cm2=dose,
            focus_nm=focus,
            resist_model="full_chem",
            grid=grid,
            se_blur_nm=se_blur,
            # Resist parameters from calibration
            # unfitted parameters stay at the SimulationConfig defaults (single
            # source of truth; hard-coded copies drifted, 2026-09-05)
            dill_C=params.get("dill_C", _defaults.dill_C),
            peb_k=params.get("peb_k", _defaults.peb_k),
            peb_t_bake=params.get("peb_t_bake", _defaults.peb_t_bake),
            peb_sigma_diff=params.get("peb_sigma_diff", _defaults.peb_sigma_diff),
            peb_acid_lifetime_s=params.get("peb_acid_lifetime_s", _defaults.peb_acid_lifetime_s),
            mack_R_max=params.get("mack_R_max", _defaults.mack_R_max),
            mack_R_min=params.get("mack_R_min", _defaults.mack_R_min),
            mack_n=params.get("mack_n", _defaults.mack_n),
            mack_M_th=params.get("mack_M_th", _defaults.mack_M_th),
        )
        result = run_simulation(cfg)
        return float(result.cd_nm)

    # Run fitting
    typer.echo("[>] Fitting resist parameters...")
    fit_result = fit_resist_params(
        data,
        initial_params,
        pipeline_fn,
        bounds=bounds,
        method=method,
        options={"maxiter": maxiter},
    )

    typer.echo(
        f"\n✅ Fit {'succeeded' if fit_result['success'] else 'failed'}: "
        f"RMSE = {fit_result['rmse']:.3f} nm"
    )
    typer.echo(f"   Iterations: {fit_result['n_iter']}, Function evals: {fit_result['nfev']}")
    typer.echo("   Fitted parameters:")
    for name, val in fit_result["fitted_params"].items():
        typer.echo(f"     {name}: {val:.4f}")

    # Bootstrap confidence intervals
    boot_result = None
    if bootstrap_samples > 0:
        typer.echo(
            f"\n[~] Running {bootstrap_samples} bootstrap samples for confidence intervals..."
        )
        boot_result = bootstrap_fit(
            data,
            pipeline_fn,
            initial_params,
            n_samples=bootstrap_samples,
            bounds=bounds,
            method=method,
            seed=seed,
        )
        valid_count = int(np.sum(~np.any(np.isnan(boot_result["bootstrap_samples"]), axis=1)))
        typer.echo(f"   Valid samples: {valid_count}/{bootstrap_samples}")
        typer.echo("   95% Confidence intervals:")
        for name in boot_result["param_names"]:
            lo = boot_result["ci_lower"][name]
            hi = boot_result["ci_upper"][name]
            fitted = boot_result["fitted_on_original"][name]
            typer.echo(f"     {name}: {fitted:.4f}  [{lo:.4f}, {hi:.4f}]")

    # Prepare output
    output_data = {
        "fit": fit_result,
        "bootstrap": boot_result,
        "data_shape": {"dose": data.n_dose, "focus": data.n_focus},
    }

    if output:
        Path(output).write_text(json.dumps(output_data, indent=2))
        typer.echo(f"\n\U0001f4c1 Results saved to {output}")
    else:
        print(json.dumps(output_data, indent=2))


# ── entry point ────────────────────────────────────────────────────────────


if __name__ == "__main__":
    app()
