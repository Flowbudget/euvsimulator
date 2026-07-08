"""Plotting utilities for EUV multilayer reflectivity.

Provides convenience functions for producing publication-quality
reflectivity plots using Matplotlib.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Tuple

import torch

from euv.optics.tmm import reflectivity, reflectivity_scan


def plot_reflectivity_spectrum(
    n_layers: torch.Tensor,
    thicknesses: torch.Tensor,
    wavelength_range: Tuple[float, float, int] = (12.0e-9, 15.0e-9, 201),
    theta0: float = math.radians(6.0),
    roughness_nm: float | None = None,
    n_substrate: torch.Tensor | None = None,
    te: bool = True,
    title: str = "EUV Multilayer Reflectivity – Wavelength Scan",
    save_path: str | None = None,
    show: bool = False,
) -> Tuple[list, list]:
    """Plot reflectivity *R* vs wavelength.

    Parameters
    ----------
    n_layers : (N,) complex128
        Layer refractive indices.
    thicknesses : (N,) float64 [m]
        Layer thicknesses.
    wavelength_range : (wl_min, wl_max, npts)
        Scan range in metres.
    theta0 : float [rad]
        Angle of incidence.
    roughness_nm : float or None
        Interface roughness [nm] for Névot–Croce damping.
    n_substrate : complex128 or None
        Substrate index.  Defaults to the last layer index.
    te : bool
        TE (True) or TM (False) polarisation.
    title : str
        Plot title.
    save_path : str or None
        If set, save the figure to this path (e.g. ``"spectrum.png"``).
    show : bool
        If True, call ``plt.show()``.

    Returns
    -------
    wavelengths_nm, R_values : list
        The raw data points (for programmatic use).
    """
    import matplotlib.pyplot as plt

    if n_substrate is None:
        n_substrate = n_layers[-1].detach().clone()

    wl, R = reflectivity_scan(
        n_layers,
        thicknesses,
        wavelength_range,
        theta0=theta0,
        n_substrate=n_substrate,
        te=te,
        roughness_nm=roughness_nm,
    )

    wl_nm = [w * 1e9 for w in wl.tolist()]
    R_list = R.tolist()

    plt.figure(figsize=(8, 5))
    plt.plot(wl_nm, R_list, "b-", linewidth=1.5)
    plt.axvline(x=13.5, color="gray", linestyle="--", alpha=0.5, label="13.5 nm")
    plt.xlabel("Wavelength [nm]")
    plt.ylabel("Reflectivity R")
    plt.title(title)
    plt.ylim(0, 1)
    plt.grid(True, alpha=0.3)
    plt.legend()

    _apply_theme(plt.gcf())
    _save_or_show(save_path, show)
    return wl_nm, R_list


def plot_reflectivity_angle(
    n_layers: torch.Tensor,
    thicknesses: torch.Tensor,
    wavelength_m: float = 13.5e-9,
    angle_range: Tuple[float, float, int] = (0.0, 20.0, 101),
    roughness_nm: float | None = None,
    n_substrate: torch.Tensor | None = None,
    te: bool = True,
    title: str = "EUV Multilayer Reflectivity – Angular Scan",
    save_path: str | None = None,
    show: bool = False,
) -> Tuple[list, list]:
    """Plot reflectivity *R* vs incidence angle.

    Parameters
    ----------
    n_layers : (N,) complex128
    thicknesses : (N,) float64 [m]
    wavelength_m : float [m]
        Fixed wavelength (default 13.5 nm).
    angle_range : (theta_min, theta_max, npts)  [deg]
        Scan range in degrees.
    roughness_nm : float or None
    n_substrate : complex128 or None
    te : bool
    title : str
    save_path : str or None
    show : bool

    Returns
    -------
    angles_deg, R_values : list
    """
    import matplotlib.pyplot as plt
    import numpy as np

    if n_substrate is None:
        n_substrate = n_layers[-1].detach().clone()

    theta_min, theta_max, npts = angle_range
    angles_rad = torch.linspace(math.radians(theta_min), math.radians(theta_max), npts)
    wl_batch = torch.full((npts,), wavelength_m, dtype=torch.float64)

    R_list = []
    for i in range(npts):
        Ri, _ = reflectivity(
            n_layers,
            thicknesses,
            wl_batch[i:i+1],
            angles_rad[i].item(),
            n_substrate=n_substrate,
            te=te,
            roughness_nm=roughness_nm,
        )
        R_list.append(Ri.item())

    angles_deg = [math.degrees(a) for a in angles_rad.tolist()]

    plt.figure(figsize=(8, 5))
    plt.plot(angles_deg, R_list, "r-", linewidth=1.5)
    plt.xlabel("Incidence Angle [deg]")
    plt.ylabel("Reflectivity R")
    plt.title(title)
    plt.ylim(0, 1)
    plt.grid(True, alpha=0.3)

    _apply_theme(plt.gcf())
    _save_or_show(save_path, show)
    return angles_deg, R_list


def plot_reflectivity(
    n_layers: torch.Tensor,
    thicknesses: torch.Tensor,
    wavelength_range: Tuple[float, float, int] = (12.0e-9, 15.0e-9, 201),
    angle_range: Tuple[float, float, int] = (0.0, 20.0, 101),
    theta0: float = math.radians(6.0),
    wavelength_m: float = 13.5e-9,
    roughness_nm: float | None = None,
    n_substrate: torch.Tensor | None = None,
    te: bool = True,
    save_path: str | None = None,
    show: bool = False,
) -> None:
    """Side-by-side spectral and angular reflectivity plots."""
    import matplotlib.pyplot as plt

    if n_substrate is None:
        n_substrate = n_layers[-1].detach().clone()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # --- Spectral scan (left) ---
    wl, R_spec = reflectivity_scan(
        n_layers, thicknesses, wavelength_range,
        theta0=theta0, n_substrate=n_substrate, te=te, roughness_nm=roughness_nm,
    )
    ax1.plot([w * 1e9 for w in wl.tolist()], R_spec.tolist(), "b-", linewidth=1.5)
    ax1.axvline(x=13.5, color="gray", linestyle="--", alpha=0.5, label="13.5 nm")
    ax1.set_xlabel("Wavelength [nm]")
    ax1.set_ylabel("Reflectivity R")
    ax1.set_title("Spectral Scan")
    ax1.set_ylim(0, 1)
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    # --- Angular scan (right) ---
    theta_min, theta_max, npts = angle_range
    angles_rad = torch.linspace(math.radians(theta_min), math.radians(theta_max), npts)
    wl_batch = torch.full((npts,), wavelength_m, dtype=torch.float64)
    R_ang = []
    for i in range(npts):
        Ri, _ = reflectivity(
            n_layers, thicknesses, wl_batch[i:i+1],
            angles_rad[i].item(),
            n_substrate=n_substrate, te=te, roughness_nm=roughness_nm,
        )
        R_ang.append(Ri.item())

    ax2.plot([math.degrees(a) for a in angles_rad.tolist()], R_ang, "r-", linewidth=1.5)
    ax2.set_xlabel("Incidence Angle [deg]")
    ax2.set_ylabel("Reflectivity R")
    ax2.set_title("Angular Scan")
    ax2.set_ylim(0, 1)
    ax2.grid(True, alpha=0.3)

    fig.suptitle("OpEnUV Multilayer Reflectivity", fontsize=14)
    _apply_theme(fig)
    _save_or_show(save_path, show)


def plot_roughness_comparison(
    n_layers: torch.Tensor,
    thicknesses: torch.Tensor,
    sigma_values: list = (0.0, 0.3, 0.5, 0.7),
    wavelength_range: Tuple[float, float, int] = (12.0e-9, 15.0e-9, 201),
    theta0: float = math.radians(6.0),
    n_substrate: torch.Tensor | None = None,
    te: bool = True,
    save_path: str | None = None,
    show: bool = False,
) -> None:
    """Compare reflectivity spectra for different interface roughness values."""
    import matplotlib.pyplot as plt

    if n_substrate is None:
        n_substrate = n_layers[-1].detach().clone()

    plt.figure(figsize=(9, 5))
    colors = ["blue", "green", "orange", "red"]

    for sigma, color in zip(sigma_values, colors):
        wl, R = reflectivity_scan(
            n_layers, thicknesses, wavelength_range,
            theta0=theta0, n_substrate=n_substrate, te=te,
            roughness_nm=sigma,
        )
        label = f"σ = {sigma:.1f} nm" if sigma > 0 else "σ = 0 (ideal)"
        plt.plot([w * 1e9 for w in wl.tolist()], R.tolist(),
                 color=color, linewidth=1.5, label=label)

    plt.axvline(x=13.5, color="gray", linestyle="--", alpha=0.4)
    plt.xlabel("Wavelength [nm]")
    plt.ylabel("Reflectivity R")
    plt.title("Effect of Interface Roughness on EUV Reflectivity")
    plt.ylim(0, 1)
    plt.grid(True, alpha=0.3)
    plt.legend()

    _apply_theme(plt.gcf())
    _save_or_show(save_path, show)


# ──────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────


def _apply_theme(fig) -> None:
    """Apply a clean, publication-ready theme."""
    try:
        import matplotlib.pyplot as plt
        plt.rcParams.update({
            "font.family": "sans-serif",
            "font.size": 11,
            "axes.titlesize": 13,
            "axes.labelsize": 12,
            "legend.fontsize": 10,
            "figure.dpi": 120,
        })
    except Exception:
        pass


def _save_or_show(save_path: str | None, show: bool) -> None:
    """Save figure and/or display."""
    import matplotlib.pyplot as plt
    if save_path:
        p = Path(save_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(str(p), dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    else:
        plt.close()


# Re-export
__all__ = [
    "plot_reflectivity_spectrum",
    "plot_reflectivity_angle",
    "plot_reflectivity",
    "plot_roughness_comparison",
]