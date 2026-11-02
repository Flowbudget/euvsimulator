#!/bin/bash
# Download CXRO Henke scattering factor tables
# These are public-domain data from the Center for X-Ray Optics (LBNL)
#
# Thin wrapper around download_cxro.py, which writes <Element>.csv into the
# directory euvsimulator.materials reads. The former body downloaded raw .nff
# files into a directory and a format that the loader never read.
set -euo pipefail

exec python3 "$(dirname "$0")/download_cxro.py" "$@"
