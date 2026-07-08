#!/usr/bin/env bash
# Run a Persona Audit workflow file through the Xenon pipelines_v2 CLI.
#
# Xenon's Modal runner mounts `pipelines_v2/` (and `papers/`) from the detected
# workspace root, so workflows must execute with the Xenon checkout as that
# root. This wrapper handles the cd + PYTHONPATH wiring so callers can stay in
# persona-audit and use repo-relative paths:
#
#   backend/scripts/run_xenon_workflow.sh plan --file backend/workflows/demo_generation.py
#   backend/scripts/run_xenon_workflow.sh run  --file backend/workflows/demo_generation.py --logging INFO
#   backend/scripts/run_xenon_workflow.sh show --run-id wr_...
#
# The Xenon checkout defaults to the sibling directory `../xenon`; override
# with XENON_WORKSPACE_ROOT (env or .env). See docs/xenon-modal-runbook.md.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

if [[ -z "${XENON_WORKSPACE_ROOT:-}" && -f "${REPO_ROOT}/.env" ]]; then
    XENON_WORKSPACE_ROOT="$(sed -n 's/^XENON_WORKSPACE_ROOT=//p' "${REPO_ROOT}/.env" | tail -1 | tr -d '"'"'")"
fi
XENON_WORKSPACE_ROOT="${XENON_WORKSPACE_ROOT:-${REPO_ROOT}/../xenon}"
XENON_WORKSPACE_ROOT="$(cd "${XENON_WORKSPACE_ROOT}" 2>/dev/null && pwd)" || {
    echo "error: Xenon checkout not found. Set XENON_WORKSPACE_ROOT or clone xenon next to this repo." >&2
    exit 1
}

if [[ $# -eq 0 ]]; then
    echo "usage: $(basename "$0") <plan|run|runs|show|resume|rerun-step|rerun-from-step> [args...]" >&2
    exit 2
fi

# Absolutize repo-relative path args (e.g. --file backend/workflows/foo.py)
# since the CLI executes with the Xenon checkout as cwd.
args=()
for arg in "$@"; do
    if [[ "$arg" != /* && -e "${REPO_ROOT}/${arg}" ]]; then
        args+=("${REPO_ROOT}/${arg}")
    else
        args+=("$arg")
    fi
done

export XENON_WORKSPACE_ROOT
export PYTHONPATH="${REPO_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
cd "${XENON_WORKSPACE_ROOT}"
exec uv run python -m pipelines_v2.cli workflow "${args[@]}"
