#!/usr/bin/env bash
set -euo pipefail

if (($# < 2)); then
  echo "Usage: $0 <python|native_r|report_integration> <python-executable> [pytest args...]" >&2
  exit 2
fi

lane="$1"
python_executable="$2"
shift 2

case "$lane" in
  python)
    required_r="0"
    required_report="0"
    ;;
  native_r)
    required_r="1"
    required_report="0"
    ;;
  report_integration)
    required_r="1"
    required_report="1"
    ;;
  *)
    echo "Unknown offline test lane: $lane" >&2
    exit 2
    ;;
esac

workspace="${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is required}"
uid="$(id -u)"
gid="$(id -g)"

# Create a network namespace as root, then drop back to the runner account
# with only the test runtime's required environment passed to the process.
exec sudo -n /usr/bin/unshare --net /usr/bin/setpriv \
  --reuid "$uid" --regid "$gid" --init-groups \
  /usr/bin/env \
  "PATH=$PATH" \
  "HOME=$HOME" \
  "PYTHONPATH=$workspace/src" \
  "R_LIBS_USER=${R_LIBS_USER:-}" \
  "FM_TEST_ARTIFACT_DIR=${FM_TEST_ARTIFACT_DIR:?FM_TEST_ARTIFACT_DIR is required}" \
  "FORENSICS_REQUIRE_R_INTEGRATION=$required_r" \
  "FORENSICS_REQUIRE_REPORT_INTEGRATION=$required_report" \
  "UV_OFFLINE=1" \
  "$python_executable" "$@"
