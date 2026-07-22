"""CLI entry point for OpEnUV (`euv` command).

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

from euv.materials import DATA_DIR

app = typer.Typer(
    name="euv",
    help="OpEnUV — Open Source EUV Lithography Simulator",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


# ── version ────────────────────────────────────────────────────────────────


@app.command()
def version():
    """Print the installed version."""
    from euv import __version__

    print(f"euv v{__version__}")


# ── info ───────────────────────────────────────────────────────────────────


@app.command()
def info():
    """Print system information and configuration overview."""
    import torch

    from euv import __version__

    print(f"OpEnUV v{__version__}")
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
    print("  • aerial/     — Abbe imaging + pupil + source shapes")
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
    print("Tests:     534 / 534 passing")
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
    # Dill ABC exposure options
    dill_A: float = typer.Option(0.5, "--dill-A", help="Bleachable absorption coefficient [1/µm]"),
    dill_B: float = typer.Option(
        0.2, "--dill-B", help="Non-bleachable absorption coefficient [1/µm]"
    ),
    dill_C: float = typer.Option(0.05, "--dill-C", help="Photo-rate constant [cm²/mJ]"),
    dill_Q: float = typer.Option(1.0, "--dill-Q", help="Quantum efficiency (max acid yield)"),
    # PEB options
    peb_D: float = typer.Option(5.0, "--peb-D", help="Acid diffusivity [nm²/s]"),
    peb_k: float = typer.Option(0.3, "--peb-k", help="Deprotection rate constant [s⁻¹]"),
    peb_t_bake: float = typer.Option(60.0, "--peb-t-bake", help="Bake time [s]"),
    peb_sigma_diff: float = typer.Option(
        5.0, "--peb-sigma-diff", help="Analytical diffusion sigma [nm]"
    ),
    # Stochastic / Shot Noise options
    enable_stochastic: bool = typer.Option(
        False, "--stochastic", help="Enable photon shot noise and LER/LWR extraction"
    ),
    stochastic_n_realisations: int = typer.Option(
        1, "--stochastic-realisations", help="Number of independent noise realisations"
    ),
    stochastic_develop_threshold: float = typer.Option(
        0.3, "--stochastic-dev-threshold", help="Development threshold for LER/LWR [0-1]"
    ),
    stochastic_quantum_efficiency: float = typer.Option(
        0.04, "--stochastic-q", help="Quantum efficiency (acid per absorbed photon)"
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
    mask_sidewall_roughness_nm: float = typer.Option(
        0.0, "--mask-sidewall-roughness", help="Sidewall roughness sigma [nm]"
    ),
    # Mack development options
    mack_R_max: float = typer.Option(100.0, "--mack-R-max", help="Max development rate [nm/s]"),
    mack_R_min: float = typer.Option(0.1, "--mack-R-min", help="Min development rate [nm/s]"),
    mack_n: float = typer.Option(5.0, "--mack-n", help="Dissolution selectivity (contrast)"),
    mack_M_th: float = typer.Option(
        0.5, "--mack-M-th", help="Threshold inhibitor concentration [0-1]"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", help="Output directory (prints to stdout if omitted)"
    ),
):
    """Run a full end-to-end simulation.

    Reads from a YAML/JSON config file, or uses command-line parameters.
    """
    from euv.pipeline import RESIST_PRESETS, SimulationConfig, run_simulation

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
            resist_threshold=threshold,
            se_blur_nm=se_blur_nm,
            resist_model=resist_model,
            # Dill ABC exposure parameters
            dill_A=dill_A,
            dill_B=dill_B,
            dill_C=dill_C,
            dill_Q=dill_Q,
            # PEB parameters
            peb_D=peb_D,
            peb_k=peb_k,
            peb_t_bake=peb_t_bake,
            peb_sigma_diff=peb_sigma_diff,
            # Mack development parameters
            mack_R_max=mack_R_max,
            mack_R_min=mack_R_min,
            mack_n=mack_n,
            mack_M_th=mack_M_th,
            # Stochastic / Shot Noise parameters
            enable_stochastic=enable_stochastic,
            stochastic_n_realisations=stochastic_n_realisations,
            stochastic_develop_threshold=stochastic_develop_threshold,
            stochastic_quantum_efficiency=stochastic_quantum_efficiency,
            stochastic_seed=stochastic_seed,
            # Mask-3D / RCWA parameters (Phase 4)
            use_rcwa=use_rcwa,
            absorber_taper_deg=absorber_taper_deg,
            mask_undercut_nm=mask_undercut_nm,
            mask_sidewall_roughness_nm=mask_sidewall_roughness_nm,
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

    from euv.pipeline import SimulationConfig, run_simulation

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

    # Compute process window metrics
    lo = target_cd * (1 - tolerance)
    hi = target_cd * (1 + tolerance)
    in_spec = (cd_matrix >= lo) & (cd_matrix <= hi)

    # Depth of focus
    dof = 0.0
    for i in range(dose_steps):
        f_ok = focuses[in_spec[i]]
        if len(f_ok) > 1:
            dof = max(dof, f_ok.max() - f_ok.min())

    # Exposure latitude
    j_best = int(np.argmax(in_spec.sum(axis=0)))
    d_ok = doses[in_spec[:, j_best]]
    el = (d_ok.max() - d_ok.min()) / target_cd * 100 if len(d_ok) > 1 else 0.0

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
    energy: float = typer.Option(91.84, "--energy", "-e", help="Photon energy [eV]"),
):
    """Query the CXRO material database.

    Without arguments: lists all available elements.
    With an element: prints refractive index at the given energy.
    """
    from euv.materials import CXROTable

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
            from euv.constants import PLANCK_CONSTANT, SPEED_OF_LIGHT

            ev_to_joule = 1.602176634e-19
            wavelength_nm = (PLANCK_CONSTANT * SPEED_OF_LIGHT) / (energy * ev_to_joule) * 1e9
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

    typer.echo(f"\U0001f680 Starting OpEnUV API server on http://{host}:{port}")
    typer.echo("   Docs: http://{host}:{port}/docs")
    uvicorn.run(
        "euv.api.main:app",
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

    from euv.pipeline import SimulationConfig, run_simulation

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
    from euv.accel.vram_budget import vram_report

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
):
    """Calibrate resist-model parameters to measured wafer CD data.

    The input data file must be CSV (dose,focus,cd columns) or JSON with
    WaferCDData format. See `euv.calibrate.wafer_fit.WaferCDData` for details.

    Fits the resist model parameters (Dill C/Q, PEB k/t_bake, Mack R_max/R_min/n/M_th)
    to minimise RMSE between simulated and measured CD across the focus-exposure matrix.
    """
    import json
    from pathlib import Path

    import numpy as np

    from euv.calibrate.wafer_fit import WaferCDData, bootstrap_fit, fit_resist_params
    from euv.pipeline import SimulationConfig, run_simulation

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
        for d, f, cd in zip(doses, foci, cd_values):
            cd_matrix[dose_to_idx[d], focus_to_idx[f]] = cd
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
            "dill_C": 0.05,
            "dill_Q": 1.0,
            "peb_k": 0.3,
            "peb_t_bake": 60.0,
            "peb_sigma_diff": 5.0,
            "mack_R_max": 100.0,
            "mack_R_min": 0.1,
            "mack_n": 5.0,
            "mack_M_th": 0.5,
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
            "dill_Q": (0.1, 2.0),
            "peb_k": (0.05, 2.0),
            "peb_t_bake": (30.0, 120.0),
            "peb_sigma_diff": (1.0, 20.0),
            "mack_R_max": (10.0, 500.0),
            "mack_R_min": (0.01, 10.0),
            "mack_n": (1.5, 20.0),
            "mack_M_th": (0.1, 0.9),
        }

    # Create pipeline function
    def pipeline_fn(dose: float, focus: float, **params) -> float:
        cfg = SimulationConfig(
            period_nm=64.0,
            line_width_nm=32.0,
            dose_mj_cm2=dose,
            focus_nm=focus,
            resist_model="full_chem",
            grid=128,
            # Resist parameters from calibration
            dill_C=params.get("dill_C", 0.05),
            dill_Q=params.get("dill_Q", 1.0),
            peb_k=params.get("peb_k", 0.3),
            peb_t_bake=params.get("peb_t_bake", 60.0),
            peb_sigma_diff=params.get("peb_sigma_diff", 5.0),
            mack_R_max=params.get("mack_R_max", 100.0),
            mack_R_min=params.get("mack_R_min", 0.1),
            mack_n=params.get("mack_n", 5.0),
            mack_M_th=params.get("mack_M_th", 0.5),
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
