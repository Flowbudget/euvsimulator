"""CLI entry point for OpEnUV (`euv` command)."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="euv",
    help="OpEnUV — Open Source EUV Lithography Simulator",
    no_args_is_help=True,
)


@app.command()
def version():
    """Print the installed version."""
    from euv import __version__

    print(f"euv v{__version__}")


@app.command()
def simulate(
    config: str = typer.Option("config.yaml", "--config", "-c", help="Configuration file"),
):
    """Run a full simulation pipeline."""
    print(f"🔬 Running simulation from {config}...")
    raise NotImplementedError("Simulation pipeline — Sprint 6")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", help="Bind address"),
    port: int = typer.Option(8000, "--port", "-p", help="Listen port"),
):
    """Start the REST API server."""
    import uvicorn

    print(f"🚀 Starting API server on {host}:{port}...")
    uvicorn.run("euv.api.server:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    app()