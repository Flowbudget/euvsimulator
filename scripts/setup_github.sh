#!/usr/bin/env bash
#
# Set up the OpEnUV GitHub presence: repository metadata, milestones, and labels.
#
# The names are human-chosen and describe the actual function of each part of
# the simulator — no "Sprint N" or "Phase N" placeholders.
#
# REQUIREMENTS
# ------------
# A GitHub token with these permissions on Flowbudget/OpEnUV:
#   - Contents:      read/write   (already granted)
#   - Issues:        read/write   (needed for milestones + labels)
#   - Administration: read/write  (needed for repo description + topics)
#
# For a fine-grained PAT: Settings -> Developer settings -> Fine-grained tokens
#   -> select repo Flowbudget/OpEnUV -> add the "Issues" and "Administration"
#   repository permissions.
# For a classic PAT: the "repo" scope covers all of the above.
#
# USAGE
# -----
#   export GITHUB_TOKEN=github_pat_xxx      # or ghp_xxx classic
#   ./scripts/setup_github.sh
#
set -euo pipefail

REPO="Flowbudget/OpEnUV"
API="https://api.github.com/repos/${REPO}"
TOKEN="${GITHUB_TOKEN:-}"

if [[ -z "$TOKEN" ]]; then
    # Fall back to the token embedded in the git remote.
    TOKEN=$(git remote get-url origin | sed 's/.*oauth2://;s/@github.*//')
fi
if [[ -z "$TOKEN" ]]; then
    echo "ERROR: set GITHUB_TOKEN or configure an oauth2 remote." >&2
    exit 1
fi

auth=(-H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json")

# Fail loudly on a permission error instead of silently continuing.
require_ok () {
  local code="$1" what="$2"
  if [[ "$code" == "403" ]]; then
    echo "    ERROR ($code): token lacks the permission for: $what" >&2
    echo "    -> grant the missing repository permission and re-run." >&2
    return 1
  fi
}

echo "==> Repository metadata"
code=$(curl -sS -o /dev/null -w "%{http_code}" -X PATCH "${auth[@]}" "$API" -d '{
  "description": "Open Source EUV Lithography Simulator — RCWA, TMM, Abbe/Hopkins imaging, resist modelling. GPU-native, Apache-2.0.",
  "homepage": "https://openeuv.readthedocs.io/"
}')
require_ok "$code" "Administration (description/homepage)" && echo "    description + homepage set ($code)"

echo "==> Topics"
code=$(curl -sS -o /dev/null -w "%{http_code}" -X PUT "${auth[@]}" "$API/topics" -d '{
  "names": ["lithography","euv","semiconductor","rcwa","optics","simulation",
            "pytorch","photonics","open-source","scientific-computing"]
}')
require_ok "$code" "Administration (topics)" && echo "    topics set ($code)"

echo "==> Milestones (human-readable, function-describing names)"
create_milestone () {
  local resp code
  resp=$(curl -sS -w "\n%{http_code}" -X POST "${auth[@]}" "$API/milestones" \
    -d "{\"title\": \"$1\", \"description\": \"$2\"}")
  code=$(printf '%s' "$resp" | tail -n1)
  if [[ "$code" == "403" ]]; then
    echo "    SKIP '$1' -> 403 (token lacks Issues permission)"
  else
    printf '%s' "$resp" | sed '$d' | python3 -c "import sys,json;d=json.load(sys.stdin);print('    +', d.get('title', d.get('message','?')))"
  fi
}
create_milestone "Foundation"              "Project scaffold, CXRO material database, physical constants, CLI"
create_milestone "Multilayer Optics"       "S-matrix transfer-matrix method, Mo/Si Bragg stack, collector"
create_milestone "Mask 3D Solver (1D)"     "1D RCWA Fourier Modal Method with stable eigenmode branch selection"
create_milestone "Mask 3D Solver (2D)"     "2D RCWA for crossed gratings: contact holes, islands, SRAM cells"
create_milestone "Layout Import"           "GDSII/OASIS import/export and polygon rasterization"
create_milestone "Aerial Image"            "Abbe partially coherent imaging, projection pupil, source shapes"
create_milestone "Hopkins Accelerator"     "Transmission cross coefficient + SOCS kernels for fast OPC loops"
create_milestone "High-NA Imaging"         "Anamorphic 4x/8x pupil, Zernike aberrations, defocus"
create_milestone "End-to-End Pipeline"     "Full mask-to-CD simulation pipeline"
create_milestone "Source Model"            "LPP tin-plasma spectrum (in-band + out-of-band) and dose model"
create_milestone "Resist Core"             "Dill exposure, secondary-electron blur, PEB, Mack development"
create_milestone "Stochastic Effects"      "Poisson shot noise, line-edge and line-width roughness"
create_milestone "Inverse Lithography"     "Differentiable forward model bridge for OpenILT"
create_milestone "Physics Benchmarks"      "Energy conservation, RCWA-vs-TMM cross-validation, convergence"
create_milestone "REST API and Web UI"     "FastAPI service, Pydantic schemas, browser dashboard"
create_milestone "CD Metrology"            "Sub-pixel CD extraction, process window, Bossung, SEM rendering"
create_milestone "GPU Acceleration"        "Device selection, VRAM budget manager, chunked Abbe"
create_milestone "Etch and Calibration"    "Empirical etch bias and scipy-based wafer calibration"
create_milestone "Documentation"           "Sphinx site, API reference, Jupyter tutorials"
create_milestone "Docker Deployment"       "Dockerfile and docker-compose for API and CLI"
create_milestone "Public Release"          "Continuous integration, PyPI packaging, v1.0"

echo "==> Labels"
create_label () {
  local resp code
  resp=$(curl -sS -w "\n%{http_code}" -X POST "${auth[@]}" "$API/labels" \
    -d "{\"name\": \"$1\", \"color\": \"$2\", \"description\": \"$3\"}")
  code=$(printf '%s' "$resp" | tail -n1)
  if [[ "$code" == "403" ]]; then
    echo "    SKIP '$1' -> 403 (token lacks Issues permission)"
  else
    printf '%s' "$resp" | sed '$d' | python3 -c "import sys,json;d=json.load(sys.stdin);print('    +', d.get('name', d.get('message','?')))"
  fi
}
create_label "physics engine"    "1d76db" "RCWA, TMM, aerial imaging, resist models"
create_label "numerics"          "5319e7" "Convergence, stability, eigen-solvers"
create_label "api"               "0e8a16" "REST API, SDK, web dashboard"
create_label "documentation"     "0075ca" "Docs, tutorials, docstrings"
create_label "performance"       "fbca04" "GPU acceleration, VRAM, runtime"
create_label "bug"               "d73a4a" "Something is not working"
create_label "enhancement"       "a2eeef" "New feature or request"
create_label "good first issue"  "7057ff" "Good for newcomers"
create_label "help wanted"       "008672" "Extra attention is welcome"
create_label "benchmark"         "c2e0c6" "Validation against published data"

echo "==> Done."
