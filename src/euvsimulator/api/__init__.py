"""euvsimulator REST API — FastAPI-based HTTP interface.

Provides endpoints for:
- Health checks (``GET /health``)
- Full simulation pipeline (``POST /simulate``)
- Material database queries (``GET /materials``, ``POST /materials/nk``)

Run with ``uvicorn euvsimulator.api.main:app`` or via the CLI: ``euv serve``.
"""

from __future__ import annotations
