"""OPC (Optical Proximity Correction) integration module.

This package provides bridges to inverse lithography tools:

- ``openilt_bridge`` — differentiable EUV forward model for gradient-based ILT
"""

from euvsimulator.opc.openilt_bridge import EUVForwardModel, run_ilt

__all__ = [
    "EUVForwardModel",
    "run_ilt",
]
