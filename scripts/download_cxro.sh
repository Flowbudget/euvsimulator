#!/bin/bash
# Download CXRO Henke scattering factor tables
# These are public-domain data from the Center for X-Ray Optics (LBNL)
set -euo pipefail

cd "$(dirname "$0")/.."

DATA_DIR="src/euv/data/henke"
mkdir -p "$DATA_DIR"

echo "Downloading CXRO Henke scattering factors (f1, f2)..."

# Elements: H through Cf (1-98)
# Each file is ~8 KB, total ~800 KB
BASE_URL="https://henke.lbl.gov/optical_constants/nf/Henke"

for Z in $(seq 1 98); do
    FILE="$DATA_DIR/f${Z}.nff"
    if [ ! -f "$FILE" ]; then
        echo -n "Downloading f${Z}.nff ... "
        curl -sL "$BASE_URL/f${Z}.nff" -o "$FILE" && echo "done" || echo "skipped (Z=$Z)"
    fi
done

echo ""
echo "CXRO data download complete: $(ls -1 $DATA_DIR/*.nff 2>/dev/null | wc -l) files"
echo "Location: $DATA_DIR"
