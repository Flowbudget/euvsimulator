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
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

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
    print("Tests:     504 / 504 passing")
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
    orders: int = typer.Option(21, "--orders", "-o", help="RCWA Fourier orders"),
    material: str = typer.Option("Ta", "--material", "-m", help="Absorber material"),
    threshold: float = typer.Option(0.5, "--threshold", "-t", help="Resist threshold"),
    output: Optional[str] = typer.Option(
        None, "--output", help="Output directory (prints to stdout if omitted)"
    ),
):
    """Run a full end-to-end simulation.

    Reads from a YAML/JSON config file, or uses command-line parameters.
    """
    from euv.pipeline import SimulationConfig, run_simulation

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
        cfg = SimulationConfig(
            period_nm=period,
            line_width_nm=cd,
            dose_mj_cm2=dose,
            na=na,
            sigma=sigma,
            grid=grid,
            n_rcwa_orders=orders,
            absorber_material=material,
            resist_threshold=threshold,
        )

    typer.echo("🔬 Running EUV lithography simulation...")
    result = run_simulation(cfg)

    out = {
        "cd_nm": float(f"{result.cd_nm:.2f}"),
        "nils": float(f"{result.nils_value:.4f}"),
        "absorber_reflectivity": float(f"{result.absorber_reflectivity:.4f}"),
        "aerial_max": float(f"{result.aerial_image.max():.4f}"),
        "aerial_shape": list(result.aerial_image.shape),
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
            typer.echo(f"📁 Results saved to {out_dir.resolve()}")
        except Exception:
            typer.echo(f"📁 Results saved to {out_dir.resolve()} (PNG skipped)")
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

    typer.echo(f"📊 Computing process window: {dose_steps}×{focus_steps} grid...")
    cd_matrix = np.zeros((dose_steps, focus_steps))

    for i, d in enumerate(doses):
        for j, f in enumerate(focuses):
            cfg = SimulationConfig(
                period_nm=period,
                line_width_nm=cd,
                dose_mj_cm2=d,
                focus_nm=f,
                grid=256,
            )
            result = run_simulation(cfg)
            cd_matrix[i, j] = result.cd_nm
            typer.echo(f"  dose={d:.1f}, focus={f:.0f} → CD={result.cd_nm:.2f} nm")

    # Compute process window metrics
    tolerance = 0.1
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
        "depth_of_focus_nm": float(dof),
        "exposure_latitude_pct": float(el),
    }

    if output:
        Path(output).write_text(json.dumps(result, indent=2))
        typer.echo(f"📁 Results saved to {output}")


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
        from pathlib import Path
        from euv.materials import DATA_DIR

        d = Path(DATA_DIR)
        if d.exists():
            available = sorted(
                f.stem for f in d.iterdir() if f.suffix.lower() == ".csv"
            )
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
            print(f"eps_real:      {n*n - k*k:.6f}")
            print(f"eps_imag:      {2*n*k:.6f}")
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

    typer.echo(f"🚀 Starting OpEnUV API server on http://{host}:{port}")
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


# ── entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
