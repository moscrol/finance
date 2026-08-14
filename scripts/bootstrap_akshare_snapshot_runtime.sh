#!/bin/zsh
set -euo pipefail

runtime_root="${AKSHARE_RUNTIME_ROOT:-/Users/a77/.local/share/finance-workbench}"
venv="${AKSHARE_VENV:-${runtime_root}/akshare-venv}"
repo_root="${FINANCE_WORKSPACE_CODE_ROOT:-/Users/a77/finance-workspace-runtime}"

if [[ "${1:-}" == "--dry-run" ]]; then
  print -r -- "python3 -m venv ${venv}"
  print -r -- "${venv}/bin/python -m pip install -r ${repo_root}/scripts/requirements-akshare-snapshot.txt"
  exit 0
fi

mkdir -p "${runtime_root}"
if [[ ! -x "${venv}/bin/python" ]]; then
  python3 -m venv "${venv}"
fi
"${venv}/bin/python" -m pip install --upgrade pip
"${venv}/bin/python" -m pip install -r "${repo_root}/scripts/requirements-akshare-snapshot.txt"
"${venv}/bin/python" -c "import akshare; print('akshare=' + akshare.__version__)"
