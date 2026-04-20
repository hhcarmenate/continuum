#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

export PATH="${HOME}/.local/bin:${HOME}/.cargo/bin:${PATH}"

if command -v uv >/dev/null 2>&1; then
  UV_BIN="$(command -v uv)"
elif [ -x "${HOME}/.local/bin/uv" ]; then
  UV_BIN="${HOME}/.local/bin/uv"
elif [ -x "${HOME}/.cargo/bin/uv" ]; then
  UV_BIN="${HOME}/.cargo/bin/uv"
else
  echo "Error: uv not found. Expected it in PATH, ${HOME}/.local/bin/uv, or ${HOME}/.cargo/bin/uv." >&2
  exit 127
fi

cd "${REPO_ROOT}"
exec "${UV_BIN}" run continuum
