"""CLI entry point for euvsimulator (`euv` command).

Usage:
    euv simulate [--config=FILE | --period=64 --cd=32 ...]
    euv make-mask --pitch=64 --cd=32 [--out=mask.gds]
    euv serve [--host=127.0.0.1 --port=8000]
    euv process-window --period=64 --cd=32 [--dose-start=10 --dose-end=19 --dose-steps=10 ...]
    euv materials [list | nk Si --energy=91.84]
    euv version
    euv bench
    euv info
    euv calibrate data.csv [--bootstrap=50]
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Optional, Sequence, TypeVar

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
    print("           and the commit history for known issues)")
    print("License:   Apache-2.0")


# ── simulate ───────────────────────────────────────────────────────────────


def _reject_unimplemented_mask_geometry(taper_deg: float, undercut_nm: float) -> None:
    """Exit with an error unless absorber taper and undercut are the defaults (90, 0).

    No mask model implements them: the thin-mask path ignores both fields and the
    RCWA path raises NotImplementedError (pipeline.py). The REST API rejects them
    (api/fields.py); the CLI does the same instead of silently ignoring them.
    """
    if taper_deg != 90.0 or undercut_nm != 0.0:
        typer.echo(
            "absorber_taper_deg / mask_undercut_nm are not implemented (only 90 and 0 are "
            f"accepted); got taper={taper_deg}, undercut={undercut_nm}",
            err=True,
        )
        raise typer.Exit(1)


# simulate options that only the full_chem resist model reads. The default
# aerial_threshold model thresholds the aerial image with --threshold alone
# (pipeline._cd_via_aerial_threshold) and ignores all of them.
_FULL_CHEM_ONLY_OPTIONS = (
    "se_blur",
    "resist_preset",
    "dill_A",
    "dill_B",
    "dill_C",
    "peb_D",
    "peb_k",
    "peb_acid_lifetime",
    "peb_temperature",
    "peb_t_bake",
    "peb_sigma_diff",
    "resist_thickness_nm",
    "develop_time_s",
    "n_develop_layers",
    "development_model",
    "stochastic_n_realisations",
    "stochastic_seed",
    "mack_R_max",
    "mack_R_min",
    "mack_n",
    "mack_M_th",
)


def _warn_full_chem_only_options(
    ctx: typer.Context, resist_model: str, names: Sequence[str]
) -> None:
    """Warn on stderr when full_chem-only options are given with aerial_threshold.

    Until 2026-10 the aerial_threshold model ignored them silently,
    e.g. a --se-blur sweep gave an unchanged process window.
    """
    if resist_model != "aerial_threshold":
        return
    # compared by name: typer ships its own copy of click, whose
    # ParameterSource is not the enum of an installed click
    given = [
        p.opts[0]
        for p in ctx.command.params
        if p.name is not None
        and p.name in names
        and getattr(ctx.get_parameter_source(p.name), "name", None)
        in ("COMMANDLINE", "ENVIRONMENT", "PROMPT")
    ]
    if given:
        typer.echo(
            f"Warning: {', '.join(given)} only act with --resist-model full_chem; "
            "the aerial_threshold model ignores them.",
            err=True,
        )


_C = TypeVar("_C")


def _config_or_exit(factory: Callable[..., _C], **kwargs: Any) -> _C:
    """Build a configuration, or exit 1 with its validation message.

    SimulationConfig rejects invalid values with ValueError (dose, resist and,
    since 2026-10, optics and geometry); the CLI reports that as an
    error message instead of a traceback.
    """
    try:
        return factory(**kwargs)
    except ValueError as exc:
        typer.echo(f"Invalid configuration: {exc}", err=True)
        raise typer.Exit(1)


@app.command()
def simulate(
    ctx: typer.Context,
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
        2.5,
        "--se-blur",
        help=(
            "full_chem only; no effect with the default aerial_threshold model. "
            "Secondary-electron blur sigma [nm]; default 2.5 = Thackeray et al. 2010 EUV-specific "
            "blur term (models: 2.1-3.3, Mack 2011); 0 = none (white per-pixel photon noise, "
            "not recommended with --stochastic)"
        ),
    ),
    resist_preset: Optional[str] = typer.Option(
        None,
        "--resist-preset",
        help=(
            "full_chem only; no effect with the default aerial_threshold model. "
            "se_blur_nm preset: CAR (2.5 nm, Thackeray 2010); nonCAR (2.5 nm) and "
            "HighNA (3 nm) are unsourced placeholders"
        ),
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
        10.947,
        "--peb-k",
        help=(
            "Deprotection rate constant [s⁻¹] at the PEB temperature, per unit relative acid; "
            "default = fit of the complete 110 °C curve of Yamamoto et al. 2011 Fig. 3, "
            "k*H0 = 0.2305 s⁻¹ at 1.4 mJ/cm², divided by the acid fraction H0 = 0.02105 that "
            "--dill-C gives there (docs/physics.md §3, pipeline.py peb_k note)"
        ),
    ),
    peb_acid_lifetime: Optional[float] = typer.Option(
        7.54,
        "--peb-acid-lifetime",
        help=(
            "Average acid lifetime [s] during PEB (first-order acid loss, Yamamoto 2011 Eq. 1); "
            "0 disables the loss"
        ),
    ),
    peb_temperature: Optional[float] = typer.Option(
        None,
        "--peb-temperature",
        help=(
            "PEB temperature [°C], 80-140: replaces --peb-k and --peb-acid-lifetime by Yamamoto "
            "2011 Polymer A's measured kinetics at that temperature (Fig. 3 fits, "
            "resist/kinetics.py); unset = explicit values"
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
        90.0,
        "--absorber-taper",
        help=(
            "Absorber sidewall angle from horizontal (90 = vertical). Not implemented: only 90 "
            "is accepted, other values are rejected"
        ),
    ),
    mask_undercut_nm: float = typer.Option(
        0.0,
        "--mask-undercut",
        help=(
            "Absorber undercut at ML interface in nm. Not implemented: only 0 is accepted, "
            "other values are rejected"
        ),
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

    Reads from a YAML/JSON config file, or uses command-line parameters. The
    resist-chemistry options (SE blur and preset, Dill, PEB, Mack, film,
    development, stochastics) act only with --resist-model full_chem; the
    default aerial_threshold model reads --threshold alone.
    """
    from euvsimulator.pipeline import RESIST_PRESETS, SimulationConfig, run_simulation

    if config is not None:
        cfg_path = Path(config)
        if cfg_path.suffix in (".yaml", ".yml"):
            import yaml

            raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        elif cfg_path.suffix == ".json":
            raw = json.loads(cfg_path.read_text(encoding="utf-8"))
        else:
            typer.echo(f"Unsupported config format: {cfg_path.suffix}", err=True)
            raise typer.Exit(1)
        if isinstance(raw, dict):
            _reject_unimplemented_mask_geometry(
                raw.get("absorber_taper_deg", 90.0), raw.get("mask_undercut_nm", 0.0)
            )
        cfg = _config_or_exit(SimulationConfig, **raw)
    else:
        _warn_full_chem_only_options(ctx, resist_model, _FULL_CHEM_ONLY_OPTIONS)
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

        _reject_unimplemented_mask_geometry(absorber_taper_deg, mask_undercut_nm)
        cfg = _config_or_exit(
            SimulationConfig,
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
            peb_temperature_c=peb_temperature,
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
        "mask_mean_reflectivity": float(f"{result.mask_mean_reflectivity:.4f}"),
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


def _process_window_warnings(
    cd_matrix: Any,
    doses: Any,
    focuses: Any,
    target_cd: float,
    tolerance: float,
    pw: dict[str, float],
) -> list[str]:
    """Caveats for a process window that the scanned grid does not resolve.

    EL and DoF are runs of in-spec grid points (``metro.process_window``).
    A run of one point gives 0 by definition, and a run that reaches the end
    of the scan gives a lower bound.  Up to 2.2.1 the CLI printed such
    numbers without comment: the README example (10-40 mJ/cm² in 5 mJ/cm²
    steps, -50..+50 nm) reported EL 0.0 % and DoF = the scan range.  The GUI
    shows the same kind of note (api/static/app.js, renderProcessWindow).

    Parameters
    ----------
    cd_matrix : np.ndarray
        CD [nm], shape ``(N_dose, N_focus)``.
    doses, focuses : np.ndarray
        Scanned doses [mJ/cm²] and focus values [nm], ascending.
    target_cd : float
        Target CD [nm].
    tolerance : float
        Fractional CD tolerance.
    pw : dict
        Result of ``metro.process_window.process_window`` for this scan.

    Returns
    -------
    list of str
        One sentence per caveat; empty when EL and DoF are resolved.
    """
    import numpy as np

    from euvsimulator.metro.process_window import _run_around

    lo, hi = target_cd * (1 - tolerance), target_cd * (1 + tolerance)
    in_spec = (cd_matrix >= lo) & (cd_matrix <= hi)
    if not in_spec.any():
        return [
            "No dose/focus pair prints within tolerance: shift or widen the dose range "
            "(--dose-start/--dose-end)."
        ]
    i_dose = int(np.argmin(np.abs(np.asarray(doses) - pw["best_dose"])))
    j_focus = int(np.argmin(np.abs(np.asarray(focuses) - pw["best_focus"])))
    warnings: list[str] = []

    el_run = _run_around(in_spec[:, j_focus], i_dose)
    if el_run is None or el_run[0] == el_run[1]:
        warnings.append(
            "Exposure latitude not resolved: fewer than two adjacent dose steps print within "
            "tolerance at best focus, so EL is 0 by definition; scan a finer dose grid around "
            f"{pw['best_dose']:.1f} mJ/cm² (--dose-start/--dose-end/--dose-steps)."
        )
    elif el_run[0] == 0 or el_run[1] == len(doses) - 1:
        warnings.append(
            "Exposure latitude is a lower bound: the in-spec dose range at best focus reaches "
            "the end of the dose scan; widen --dose-start/--dose-end."
        )

    dof_run = _run_around(in_spec[i_dose, :], j_focus)
    if dof_run is None or dof_run[0] == dof_run[1]:
        warnings.append(
            "Depth of focus not resolved: fewer than two adjacent focus steps print within "
            "tolerance at the best dose, so DoF is 0 by definition; scan a finer focus grid "
            "(--focus-steps)."
        )
    elif dof_run[0] == 0 or dof_run[1] == len(focuses) - 1:
        warnings.append(
            "Depth of focus saturated: the in-spec focus range at the best dose reaches the "
            "end of the focus scan, so DoF is a lower bound; widen --focus-start/--focus-end."
        )
    return warnings


@app.command(name="process-window")
def process_window(
    ctx: typer.Context,
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
    se_blur: float = typer.Option(
        2.5,
        "--se-blur",
        help=(
            "full_chem only; no effect with the default aerial_threshold model. "
            "Secondary-electron blur sigma [nm] (default: Thackeray 2010)"
        ),
    ),
    resist_model: str = typer.Option(
        "aerial_threshold", "--resist-model", help="Resist model: aerial_threshold or full_chem"
    ),
):
    """Compute a process window (Bossung plot) over dose × focus.

    Runs multiple simulations across a dose-focus grid and extracts
    depth of focus (DoF) and exposure latitude (EL).
    """
    import numpy as np

    from euvsimulator.pipeline import SimulationConfig, run_simulation

    _warn_full_chem_only_options(ctx, resist_model, ("se_blur",))
    # Same ranges the REST API accepts (api/schemas.py ProcessWindowParams).
    # A reversed range used to run the whole grid and then report a negative
    # exposure latitude or DoF = 0 as a result.
    range_errors = []
    if not dose_start < dose_end:
        range_errors.append(f"--dose-start ({dose_start}) must be smaller than --dose-end")
    if not focus_start < focus_end:
        range_errors.append(f"--focus-start ({focus_start}) must be smaller than --focus-end")
    if dose_steps < 2:
        range_errors.append(f"--dose-steps must be >= 2, got {dose_steps}")
    if focus_steps < 2:
        range_errors.append(f"--focus-steps must be >= 2, got {focus_steps}")
    if range_errors:
        typer.echo("; ".join(range_errors), err=True)
        raise typer.Exit(1)

    doses = np.linspace(dose_start, dose_end, dose_steps)
    focuses = np.linspace(focus_start, focus_end, focus_steps)
    target_cd = cd

    typer.echo(f"\U0001f4ca Computing process window: {dose_steps}×{focus_steps} grid...")
    cd_matrix = np.zeros((dose_steps, focus_steps))
    nils_matrix = np.zeros((dose_steps, focus_steps))

    for i, d in enumerate(doses):
        for j, f in enumerate(focuses):
            cfg = _config_or_exit(
                SimulationConfig,
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
    warnings = _process_window_warnings(cd_matrix, doses, focuses, target_cd, tolerance, pw)

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
    for w in warnings:
        typer.echo(f"Warning: {w}", err=True)

    pw_result: dict[str, Any] = {
        "target_cd_nm": float(target_cd),
        "doses": doses.tolist(),
        "focuses": focuses.tolist(),
        "cd_matrix": cd_matrix.tolist(),
        "nils_matrix": nils_matrix.tolist(),
        "depth_of_focus_nm": float(dof),
        "exposure_latitude_pct": float(el),
        "tolerance": tolerance,
        "warnings": warnings,
    }

    if output:
        Path(output).write_text(json.dumps(pw_result, indent=2))
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

        with open(output_csv, "w", newline="") as fh:
            writer = csv.writer(fh)
            # Header row
            writer.writerow([""] + [f"{d:.1f}" for d in doses])
            # Data rows
            for j, foc in enumerate(focuses):
                row_vals = [f"{foc:.0f}"] + [f"{cd_matrix[i, j]:.2f}" for i in range(dose_steps)]
                writer.writerow(row_vals)
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
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        help="Bind address; 127.0.0.1 = this machine only (default). 0.0.0.0 serves the local "
        "network -- the server has no authentication, use it only on a trusted network",
    ),
    port: int = typer.Option(8000, "--port", "-p", help="Listen port"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Auto-reload on changes"),
):
    """Start the browser GUI and REST API server."""
    import uvicorn

    shown = "localhost" if host in ("0.0.0.0", "::") else host
    if host in ("0.0.0.0", "::"):
        typer.echo("   Warning: listening on all interfaces without authentication.")
    typer.echo(f"\U0001f680 euvsimulator server on http://{shown}:{port}")
    typer.echo(f"   GUI:  http://{shown}:{port}/")
    typer.echo(f"   Docs: http://{shown}:{port}/docs")
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

# The resist parameters `euv calibrate` can fit, i.e. the keys an
# --initial-params file may hold. Until 2026-10 any other key was dropped on
# the way to SimulationConfig while Nelder-Mead still moved it, and the CLI
# reported it as fitted with a confidence interval.
CALIBRATE_FITTABLE = (
    "dill_C",
    "peb_k",
    "peb_t_bake",
    "peb_sigma_diff",
    "peb_acid_lifetime_s",
    "mack_R_max",
    "mack_R_min",
    "mack_n",
    "mack_M_th",
)


@app.command(name="calibrate")
def calibrate(
    data_file: str = typer.Argument(..., help="Path to wafer CD data (CSV or JSON)"),
    initial_params_file: Optional[str] = typer.Option(
        None,
        "--initial-params",
        "-i",
        help=(
            "YAML/JSON file with initial parameter guesses; its keys are the fitted set, "
            "any of: " + ", ".join(CALIBRATE_FITTABLE)
        ),
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
    bands: bool = typer.Option(
        False,
        "--bands/--no-bands",
        help=(
            "After the fit, evaluate the structural uncertainty of the calibrated chain: "
            "dose-to-size under both PEB acid-loss laws and 3-sigma LWR with/without "
            "dissolution-cell noise (cells 1 and 4.3 nm); ~3-5 min at grid 128 (calibrate/bands.py)"
        ),
    ),
    period: float = typer.Option(
        64.0, "--period", help="Pattern period of the measured FEM [nm] (wafer scale)"
    ),
    cd: float = typer.Option(32.0, "--cd", help="Nominal line width of the measured FEM [nm]"),
    grid: int = typer.Option(128, "--grid", help="Simulation grid for the fit"),
    se_blur: float = typer.Option(
        2.5, "--se-blur", help="Secondary-electron blur sigma [nm] held fixed during the fit"
    ),
):
    """Calibrate resist-model parameters to measured wafer CD data.

    The simulated geometry (--period/--cd) MUST match the measured pattern:
    until 2026-09-04 it was hard-wired to 64/32 nm regardless of the data.

    The input data file must be CSV with the columns dose, focus, cd_nm and one
    row per cell of a complete dose x focus grid (no gaps, no duplicates; leave
    cd_nm empty for a site without a measurement, e.g. one that did not print:
    the fit skips it), or JSON/YAML in WaferCDData format (null = no
    measurement). See `euvsimulator.calibrate.wafer_fit.WaferCDData` for details.

    Fits the resist model parameters (Dill C, PEB k/t_bake/sigma_diff/acid
    lifetime, Mack R_max/R_min/n/M_th) to minimise RMSE between simulated and
    measured CD across the focus-exposure matrix. Restrict the fitted set with an
    initial-parameter file: an 8-parameter fit against a small FEM is
    under-determined. Other keys are rejected; every parameter that is not
    fitted stays at its SimulationConfig default.
    """
    import json
    from pathlib import Path

    import numpy as np

    from euvsimulator.calibrate.wafer_fit import (
        DEFAULT_BOUNDS,
        WaferCDData,
        bootstrap_fit,
        fit_resist_params,
    )
    from euvsimulator.pipeline import SimulationConfig, run_simulation

    # Load wafer data
    data_path = Path(data_file)
    if data_path.suffix.lower() == ".csv":
        # CSV format: dose,focus,cd_nm
        import csv
        import math

        doses = []
        foci = []
        cd_values = []
        with open(data_path, "r") as f:
            reader = csv.DictReader(f)
            # A wrong header used to end in a raw KeyError traceback.
            absent = [c for c in ("dose", "focus", "cd_nm") if c not in (reader.fieldnames or [])]
            if absent:
                typer.echo(
                    f"{data_path} lacks the columns {absent}; the header must name dose, focus "
                    f"and cd_nm (found {reader.fieldnames}).",
                    err=True,
                )
                raise typer.Exit(1)
            for row in reader:
                # An empty or 'nan' cd_nm is a site without a measurement (NaN):
                # WaferCDData and objective_resist skip it, like a JSON null.
                cd_text = (row["cd_nm"] or "").strip()
                try:
                    dose_val = float(row["dose"])
                    focus_val = float(row["focus"])
                    cd_val = float(cd_text) if cd_text else float("nan")
                    if not (math.isfinite(dose_val) and math.isfinite(focus_val)):
                        raise ValueError("dose and focus must be finite")
                except (TypeError, ValueError):
                    typer.echo(
                        f"{data_path}, line {reader.line_num}: dose and focus must be numbers "
                        "and cd_nm a number or empty (no measurement); got "
                        f"{row['dose']!r}, {row['focus']!r}, {row['cd_nm']!r}.",
                        err=True,
                    )
                    raise typer.Exit(1)
                if math.isinf(cd_val):
                    typer.echo(
                        f"{data_path}, line {reader.line_num}: cd_nm is {cd_val}; leave it empty "
                        "for a site without a measurement.",
                        err=True,
                    )
                    raise typer.Exit(1)
                doses.append(dose_val)
                foci.append(focus_val)
                cd_values.append(cd_val)
        # Reconstruct the matrix. Every (dose, focus) cell must occur exactly
        # once: a missing cell used to stay at 0 nm and was fitted as a real
        # measurement, and a duplicate row silently overwrote the first one.
        dose_vals = sorted(set(doses))
        focus_vals = sorted(set(foci))
        cd_matrix = np.full((len(dose_vals), len(focus_vals)), np.nan)
        dose_to_idx = {d: i for i, d in enumerate(dose_vals)}
        focus_to_idx = {f: i for i, f in enumerate(focus_vals)}
        filled: set[tuple[int, int]] = set()
        # NB: do not name the loop variable `cd` -- it would shadow the --cd
        # option and silently feed the last measured CD into the simulated
        # line width (found 2026-09-05 by the synthetic-FEM smoke test).
        for d, foc, cd_meas in zip(doses, foci, cd_values):
            cell = (dose_to_idx[d], focus_to_idx[foc])
            if cell in filled:
                typer.echo(
                    f"Duplicate row for dose={d:g}, focus={foc:g} in {data_path}; "
                    "average repeated measurements before calibrating.",
                    err=True,
                )
                raise typer.Exit(1)
            filled.add(cell)
            cd_matrix[cell] = cd_meas
        # A cell without a row is still an error (a mistyped dose or focus
        # would otherwise add a whole empty axis value). The advice used to be
        # "enter a site that did not print as cd_nm 0", which fits a 0 nm CD
        # where the full_chem model reports the pitch for an underexposed site.
        missing = [
            (dose_vals[i], focus_vals[j])
            for i in range(len(dose_vals))
            for j in range(len(focus_vals))
            if (i, j) not in filled
        ]
        if missing:
            listed = "; ".join(f"dose={d:g}, focus={foc:g}" for d, foc in missing[:5])
            more = f" (+{len(missing) - 5} more)" if len(missing) > 5 else ""
            typer.echo(
                f"{len(missing)} of {cd_matrix.size} (dose, focus) cells in {data_path} have "
                f"no row: {listed}{more}. The CSV must hold the complete grid; for a site "
                "without a measurement (e.g. one that did not print) leave cd_nm empty.",
                err=True,
            )
            raise typer.Exit(1)
        n_unmeasured = int(np.isnan(cd_matrix).sum())
        if n_unmeasured == cd_matrix.size:
            typer.echo(f"{data_path} holds no finite cd_nm value; nothing to fit.", err=True)
            raise typer.Exit(1)
        if n_unmeasured:
            typer.echo(
                f"   {n_unmeasured} of {cd_matrix.size} sites have no measurement (empty or nan "
                "cd_nm) and are skipped by the fit."
            )
        data = WaferCDData(
            dose_values=np.array(dose_vals),
            focus_values=np.array(focus_vals),
            cd_matrix_nm=cd_matrix,
        )
    elif data_path.suffix.lower() in (".json", ".yaml", ".yml"):
        import yaml

        raw = (
            yaml.safe_load(data_path.read_text(encoding="utf-8"))
            if data_path.suffix.lower() in (".yaml", ".yml")
            else json.loads(data_path.read_text(encoding="utf-8"))
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
            yaml.safe_load(ip_path.read_text(encoding="utf-8"))
            if ip_path.suffix.lower() in (".yaml", ".yml")
            else json.loads(ip_path.read_text(encoding="utf-8"))
        )
    else:
        # Default initial guess for typical EUV CAR resist
        initial_params = {
            "dill_C": 0.0152,  # LBNL MET-2D, direct measurement (see pipeline.py dill_C comment)
            "peb_k": 10.947,  # Yamamoto 2011 Fig. 3 full-curve fit (see pipeline.py peb_k)
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
    if not isinstance(initial_params, dict) or not initial_params:
        typer.echo(f"{initial_params_file} must map parameter names to start values.", err=True)
        raise typer.Exit(1)
    unknown = sorted(set(initial_params) - set(CALIBRATE_FITTABLE))
    if unknown:
        typer.echo(
            f"Cannot fit {unknown}: they do not reach the simulation. Fittable parameters: "
            f"{', '.join(CALIBRATE_FITTABLE)}.",
            err=True,
        )
        raise typer.Exit(1)

    # Load bounds
    if bounds_file:
        import yaml

        b_path = Path(bounds_file)
        bounds = (
            yaml.safe_load(b_path.read_text(encoding="utf-8"))
            if b_path.suffix.lower() in (".yaml", ".yml")
            else json.loads(b_path.read_text(encoding="utf-8"))
        )
    else:
        bounds = dict(DEFAULT_BOUNDS)

    # Create pipeline function. The geometry and blur are fixed; the fitted
    # resist parameters (only CALIBRATE_FITTABLE keys, checked above) are passed
    # through unchanged and every other parameter stays at its SimulationConfig
    # default (single source of truth; hard-coded copies drifted, 2026-09-05).
    fixed: dict[str, Any] = dict(period_nm=period, line_width_nm=cd, se_blur_nm=se_blur)
    # Validate the geometry and the start values once: inside the fit a
    # ValueError only becomes a warning and a CD of 0 nm per site.
    _config_or_exit(
        SimulationConfig, **fixed, resist_model="full_chem", grid=grid, **initial_params
    )

    def pipeline_fn(dose: float, focus: float, **params) -> float:
        cfg = SimulationConfig(
            **fixed,
            dose_mj_cm2=dose,
            focus_nm=focus,
            resist_model="full_chem",
            grid=grid,
            **params,
        )
        result = run_simulation(cfg)
        return float(result.cd_nm)

    # Run fitting
    typer.echo("[>] Fitting resist parameters...")
    fit_result: dict[str, Any] = fit_resist_params(
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
    boot_result: dict[str, Any] | None = None
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
            # same iteration budget as the reported fit, and that fit itself as
            # the point estimate of the intervals (was a second fit at maxiter 1000)
            options={"maxiter": maxiter},
            original_fit=fit_result,
        )
        valid_count = int(np.sum(~np.any(np.isnan(boot_result["bootstrap_samples"]), axis=1)))
        typer.echo(f"   Valid samples: {valid_count}/{bootstrap_samples}")
        typer.echo("   95% Confidence intervals:")
        for name in boot_result["param_names"]:
            lo = boot_result["ci_lower"][name]
            hi = boot_result["ci_upper"][name]
            fitted = boot_result["fitted_on_original"][name]
            typer.echo(f"     {name}: {fitted:.4f}  [{lo:.4f}, {hi:.4f}]")

    band_result = None
    if bands:
        from euvsimulator.calibrate.bands import structural_bands

        typer.echo(
            "\n[~] Structural uncertainty bands (both PEB laws, dissolution cells 1 / 4.3 nm)..."
        )
        # The chain the fit calibrated: same fixed geometry and blur as
        # pipeline_fn plus every fitted parameter (a fitted peb_acid_lifetime_s
        # was missing here until 2026-10, so the bands ran at the default 7.54 s).
        base = {**fixed, **fit_result["fitted_params"]}
        band_result = structural_bands(base, target_cd_nm=cd, grid=grid)
        d2s = band_result["dose_to_size_mj_cm2"]
        typer.echo(
            "   dose-to-size: "
            + ", ".join(f"{k} {v:.2f}" for k, v in d2s.items())
            + f"  -> band {band_result['dose_to_size_band']}"
        )
        typer.echo(
            "   LWR 3sigma [nm]: "
            + ", ".join(
                f"{k} {v:.2f}" for k, v in band_result["lwr_3sigma_nm_at_analytical_d2s"].items()
            )
            + f"  -> band {band_result['lwr_3sigma_band']}"
        )

    # Prepare output
    output_data = {
        "fit": fit_result,
        "bootstrap": boot_result,
        "structural_bands": band_result,
        "data_shape": {"dose": data.n_dose, "focus": data.n_focus},
    }

    def _json_default(obj: Any) -> Any:
        # bootstrap_fit returns the (n_samples, P) replicas as an ndarray; without
        # this hook json.dumps raised TypeError after the whole fit had run.
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.generic):
            return obj.item()
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    if output:
        Path(output).write_text(json.dumps(output_data, indent=2, default=_json_default))
        typer.echo(f"\n\U0001f4c1 Results saved to {output}")
    else:
        print(json.dumps(output_data, indent=2, default=_json_default))


# ── entry point ────────────────────────────────────────────────────────────


if __name__ == "__main__":
    app()
