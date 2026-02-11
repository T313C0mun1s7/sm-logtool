#!/usr/bin/env bash

set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_PYTHON="$ROOT_DIR/.venv/bin/python"
PYTHON_BIN="${PYTHON_BIN:-$DEFAULT_PYTHON}"
OUTPUT_DIR=""
KEEP_WORKDIR=0
SKIP_SUITE=0

usage() {
  cat <<'EOF'
Run a CLI regression matrix with per-case logs.

Usage:
  scripts/run_cli_matrix.sh [options]

Options:
  --python PATH       Python executable to use.
  --output-dir PATH   Write artifacts to this directory.
  --keep-workdir      Keep generated temp logs/workdir.
  --skip-suite        Skip pytest/unittest cases.
  -h, --help          Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --python)
      PYTHON_BIN="$2"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --keep-workdir)
      KEEP_WORKDIR=1
      shift
      ;;
    --skip-suite)
      SKIP_SUITE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python not executable: $PYTHON_BIN" >&2
  exit 2
fi

if [[ -z "$OUTPUT_DIR" ]]; then
  stamp="$(date +%Y%m%d_%H%M%S)"
  OUTPUT_DIR="$ROOT_DIR/artifacts/cli-matrix-$stamp"
fi

mkdir -p "$OUTPUT_DIR/cases"
SUMMARY_FILE="$OUTPUT_DIR/summary.txt"

WORKDIR="$(mktemp -d /tmp/sm-cli-matrix.XXXXXX)"
LOGS_DIR="$WORKDIR/logs"
STAGING_DIR="$WORKDIR/staging"
mkdir -p "$LOGS_DIR" "$STAGING_DIR"

cleanup() {
  if [[ "$KEEP_WORKDIR" -eq 0 ]]; then
    rm -rf "$WORKDIR"
  fi
}
trap cleanup EXIT

cat > "$LOGS_DIR/2026.02.09-smtpLog.log" <<'EOF'
00:00:00 [1.1.1.1][MSG1] cmd: EHLO example.com
00:00:01 [1.1.1.1][MSG1] rsp: 250 Success
EOF

cat > "$LOGS_DIR/2026.02.10-smtpLog.log" <<'EOF'
00:00:00 [2.2.2.2][MSG2] cmd: EHLO example.org
00:00:01 [2.2.2.2][MSG2] rsp: 550 failed
EOF

cat > "$LOGS_DIR/2026.02.10-imapRetrieval.log" <<'EOF'
00:00:01.100 [72] [user; host:other] Connection refused
   at System.Net.Sockets.Socket.Connect(EndPoint remoteEP)
EOF

cat > "$LOGS_DIR/2026.02.10-imapLog.log" <<'EOF'
00:00:00 [3.3.3.3][IMAP1] IMAP Login failed
EOF

cat > "$LOGS_DIR/2026.02.10-administrative.log" <<'EOF'
10:13:13.367 [23.127.140.125] IMAP Login failed
EOF

LOGS_DIR="$LOGS_DIR" "$PYTHON_BIN" - <<'PY'
import os
from pathlib import Path
from zipfile import ZipFile

logs_dir = Path(os.environ["LOGS_DIR"])
zip_path = logs_dir / "2026.02.08-smtpLog.log.zip"
with ZipFile(zip_path, "w") as archive:
    archive.writestr(
        "2026.02.08-smtpLog.log",
        "00:00:00 [9.9.9.9][ZIP1] cmd: EHLO zipped.example\n",
    )
PY

CLI_CMD="$PYTHON_BIN -m sm_logtool.cli"
COMMON_ARGS="--logs-dir \"$LOGS_DIR\" --staging-dir \"$STAGING_DIR\""
CASE_TOTAL=0
CASE_FAILED=0

{
  echo "CLI Matrix Run"
  echo "Started: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "Repo: $ROOT_DIR"
  echo "Python: $PYTHON_BIN"
  echo "Output Dir: $OUTPUT_DIR"
  echo "Temp Workdir: $WORKDIR"
  echo
  printf "%-4s %-6s %-11s %-11s %-40s %s\n" \
    "ID" "Result" "Expected" "Observed" "Case" "Log"
  printf "%s\n" \
    "---------------------------------------------------------------------"
} > "$SUMMARY_FILE"

slugify() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '_'
}

run_case() {
  local name="$1"
  local expected_exit="$2"
  local command="$3"
  shift 3
  local patterns=("$@")

  CASE_TOTAL=$((CASE_TOTAL + 1))
  local case_id
  case_id="$(printf "%02d" "$CASE_TOTAL")"
  local slug
  slug="$(slugify "$name")"
  local log_file="$OUTPUT_DIR/cases/${case_id}_${slug}.log"

  {
    echo "Case: $name"
    echo "Expected exit: $expected_exit"
    echo "Command: $command"
    echo "Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo "---- output ----"
  } > "$log_file"

  bash -lc "$command" >> "$log_file" 2>&1
  local observed_exit=$?

  {
    echo
    echo "---- result ----"
    echo "Observed exit: $observed_exit"
  } >> "$log_file"

  local result="PASS"
  if [[ "$observed_exit" -ne "$expected_exit" ]]; then
    result="FAIL"
    {
      echo "Exit code mismatch."
      echo "Expected: $expected_exit"
      echo "Observed: $observed_exit"
    } >> "$log_file"
  fi

  local pattern
  for pattern in "${patterns[@]}"; do
    if ! grep -Fq -- "$pattern" "$log_file"; then
      result="FAIL"
      echo "Missing expected text: $pattern" >> "$log_file"
    fi
  done

  if [[ "$result" == "FAIL" ]]; then
    CASE_FAILED=$((CASE_FAILED + 1))
  fi

  printf "%-4s %-6s %-11s %-11s %-40s %s\n" \
    "$case_id" "$result" "$expected_exit" "$observed_exit" \
    "$name" "$log_file" >> "$SUMMARY_FILE"
}

if [[ "$SKIP_SUITE" -eq 0 ]]; then
  run_case \
    "Pytest suite" \
    0 \
    "$PYTHON_BIN -m pytest -q"

  run_case \
    "Unittest suite" \
    0 \
    "$PYTHON_BIN -m unittest discover test" \
    "OK"
fi

run_case \
  "CLI help" \
  0 \
  "$CLI_CMD --help" \
  "search"

run_case \
  "Search help" \
  0 \
  "$CLI_CMD search --help" \
  "--date" \
  "--log-file"

run_case \
  "List smtp logs" \
  0 \
  "$CLI_CMD search $COMMON_ARGS --kind smtp --list" \
  "Available smtp logs"

run_case \
  "Newest smtp search" \
  0 \
  "$CLI_CMD search EHLO $COMMON_ARGS --kind smtp" \
  "=== 2026.02.10-smtpLog.log ==="

run_case \
  "Single-date smtp search" \
  0 \
  "$CLI_CMD search EHLO $COMMON_ARGS --kind smtp --date 2026.02.09" \
  "=== 2026.02.09-smtpLog.log ==="

run_case \
  "Multi-date smtp search" \
  0 \
  "$CLI_CMD search EHLO $COMMON_ARGS --kind smtp --date 2026.02.09 \
--date 2026.02.10" \
  "=== 2026.02.09-smtpLog.log ===" \
  "=== 2026.02.10-smtpLog.log ==="

run_case \
  "Multi-log-file smtp search" \
  0 \
  "$CLI_CMD search EHLO $COMMON_ARGS --kind smtp \
--log-file 2026.02.09-smtpLog.log --log-file 2026.02.10-smtpLog.log" \
  "=== 2026.02.09-smtpLog.log ===" \
  "=== 2026.02.10-smtpLog.log ==="

run_case \
  "Zip log date search" \
  0 \
  "$CLI_CMD search EHLO $COMMON_ARGS --kind smtp --date 2026.02.08" \
  "=== 2026.02.08-smtpLog.log.zip ==="

run_case \
  "IMAP retrieval search" \
  0 \
  "$CLI_CMD search Socket.Connect $COMMON_ARGS --kind imapretrieval \
--date 2026.02.10" \
  "=== 2026.02.10-imapRetrieval.log ==="

run_case \
  "No matches output" \
  0 \
  "$CLI_CMD search does-not-exist $COMMON_ARGS --kind smtp \
--date 2026.02.09" \
  "No matches found."

run_case \
  "Case-sensitive no-match" \
  0 \
  "$CLI_CMD search ehlo --case-sensitive $COMMON_ARGS --kind smtp \
--date 2026.02.09" \
  "No matches found."

run_case \
  "Reject mixed date and log-file" \
  2 \
  "$CLI_CMD search EHLO $COMMON_ARGS --kind smtp --date 2026.02.09 \
--log-file 2026.02.09-smtpLog.log" \
  "--log-file and --date cannot be used together."

run_case \
  "Reject mismatched file kind" \
  2 \
  "$CLI_CMD search EHLO $COMMON_ARGS --kind smtp \
--log-file 2026.02.10-imapLog.log" \
  "does not match kind smtp."

run_case \
  "Reject invalid date format" \
  2 \
  "$CLI_CMD search EHLO $COMMON_ARGS --kind smtp --date 2026-02-09" \
  "Invalid log date stamp"

run_case \
  "Reject unsupported kind" \
  2 \
  "$CLI_CMD search EHLO $COMMON_ARGS --kind unknownKind --date 2026.02.09" \
  "Unsupported log kind"

{
  echo
  echo "Total cases: $CASE_TOTAL"
  echo "Failed cases: $CASE_FAILED"
  echo "Finished: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
} >> "$SUMMARY_FILE"

echo "CLI matrix complete."
echo "Summary: $SUMMARY_FILE"
echo "Case logs: $OUTPUT_DIR/cases"
if [[ "$KEEP_WORKDIR" -eq 1 ]]; then
  echo "Fixture workdir kept at: $WORKDIR"
fi

if [[ "$CASE_FAILED" -ne 0 ]]; then
  exit 1
fi

exit 0
