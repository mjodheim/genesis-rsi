#!/usr/bin/env bash
# Run tests in a disposable worktree so research fixtures cannot be mutated
# in the original tracked checkout. Does not substitute for CI.
set -euo pipefail
seconds="$(printenv GENESIS_PYTEST_TIMEOUT_SECONDS || true)"
if [[ -z "$seconds" ]]; then seconds=300; fi
if [[ $# -ge 1 && "$1" == "--timeout" ]]; then
  if [[ $# -lt 2 ]]; then echo "Missing timeout" >&2; exit 64; fi
  seconds="$2"
  shift 2
fi
if [[ ! "$seconds" =~ ^[1-9][0-9]*$ ]] || (( seconds > 7200 )); then
  echo "Timeout must be positive and at most 7200 seconds" >&2; exit 64
fi
source_root="$(git rev-parse --show-toplevel)"
cd "$source_root"
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Refusing dirty source worktree" >&2; exit 65
fi
python="$(printenv GENESIS_TEST_PYTHON || true)"
if [[ -z "$python" ]]; then python=python3; fi
if ! command -v "$python" >/dev/null 2>&1; then
  echo "Missing Python interpreter: $python" >&2; exit 69
fi
tmpbase="$(printenv TMPDIR || true)"
if [[ -z "$tmpbase" ]]; then tmpbase=/tmp; fi
temp="$(mktemp -d "$tmpbase/genesis-isolated-pytest.XXXXXXXX")"
rmdir "$temp"
status_file="$(mktemp "$tmpbase/genesis-side-effects.XXXXXXXX")"
cleanup() {
  git -C "$source_root" worktree remove --force "$temp"
  rm -f -- "$status_file"
}
trap cleanup EXIT
git -C "$source_root" worktree add --detach "$temp" HEAD >/dev/null
echo "ISOLATED_TEST_WORKTREE=$temp"
set +e
(
  cd "$temp"
  PYTHONPATH="$temp" timeout "$seconds" "$python" -m pytest -q "$@"
)
rc=$?
set -e
git -C "$temp" status --porcelain=v1 --untracked-files=all > "$status_file"
count="$(wc -l < "$status_file")"
tracked_count="$(git -C "$temp" diff --name-only HEAD -- | wc -l)"
echo "ISOLATED_TEST_SIDE_EFFECT_PATHS=$count"
echo "ISOLATED_TEST_TRACKED_SIDE_EFFECT_PATHS=$tracked_count"
if [[ -s "$status_file" ]]; then
  echo "ISOLATED_TEST_SIDE_EFFECT_MANIFEST_BEGIN"
  sed 's/^/ISOLATED_TEST_SIDE_EFFECT /' "$status_file"
  echo "ISOLATED_TEST_SIDE_EFFECT_MANIFEST_END"
fi
echo "ISOLATED_TEST_EXIT=$rc"
exit "$rc"
