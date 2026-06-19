#!/bin/zsh
set -u

SCRIPT_DIR="${0:A:h}"
PROJECT_DIR="${SCRIPT_DIR}"
PYTHON="$PROJECT_DIR/.venv/bin/python"
MAIN_SCRIPT="$PROJECT_DIR/meet_automation.py"
LOG_ROOT="$PROJECT_DIR/logs"
RUNS_DIR="$LOG_ROOT/recurring_schedule_runs"

usage() {
    cat <<'EOF'
Usage:
  run_scheduled_meet.sh --config <path>
EOF
}

CONFIG_PATH=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --config)
            CONFIG_PATH="$2"
            shift 2
            ;;
        *)
            usage >&2
            exit 1
            ;;
    esac
done

if [[ -z "$CONFIG_PATH" ]]; then
    usage >&2
    exit 1
fi

if [[ ! -x "$PYTHON" ]]; then
    printf '[%s] ERROR: Python executable not found at %s\n' \
        "$(/bin/date '+%Y-%m-%d %H:%M:%S')" "$PYTHON" >&2
    exit 1
fi

if [[ ! -f "$MAIN_SCRIPT" ]]; then
    printf '[%s] ERROR: Main script not found at %s\n' \
        "$(/bin/date '+%Y-%m-%d %H:%M:%S')" "$MAIN_SCRIPT" >&2
    exit 1
fi

if [[ ! -f "$CONFIG_PATH" ]]; then
    printf '[%s] ERROR: Schedule config not found at %s\n' \
        "$(/bin/date '+%Y-%m-%d %H:%M:%S')" "$CONFIG_PATH" >&2
    exit 1
fi

mkdir -p "$RUNS_DIR"
RUN_TIMESTAMP=$(/bin/date '+%Y%m%d_%H%M%S')
LOG_DIR="$RUNS_DIR/$RUN_TIMESTAMP"
mkdir -p "$LOG_DIR"

export MEET_AUTOMATION_LOG_DIR="$LOG_DIR"

exec >> "$LOG_DIR/launchd_stdout.log" 2>> "$LOG_DIR/launchd_stderr.log"

printf '[%s] Recurring LaunchAgent process started. PID: %s\n' \
    "$(/bin/date '+%Y-%m-%d %H:%M:%S')" "$$"

cd "$PROJECT_DIR" || {
    printf '[%s] ERROR: Could not enter project directory.\n' \
        "$(/bin/date '+%Y-%m-%d %H:%M:%S')"
    exit 1
}

"$PYTHON" "$MAIN_SCRIPT" run-scheduled-job --config "$CONFIG_PATH"
EXIT_CODE=$?

printf '[%s] Automation exited with code %s\n' \
    "$(/bin/date '+%Y-%m-%d %H:%M:%S')" "$EXIT_CODE"
exit "$EXIT_CODE"
