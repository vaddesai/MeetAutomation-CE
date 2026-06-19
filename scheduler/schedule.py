#!/usr/bin/env python3

import json
import plistlib
import re
import shlex
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

from common.config import BASE_DIR, DEFAULT_CHROME_USER_DATA_DIR, list_chrome_profiles
from common.logging_utils import log_phase, run_osascript


SCHEDULE_CONFIG_PATH = BASE_DIR / ".meet_automation_schedule.json"
SCHEDULE_LABEL = "com.user.meet.scheduledjoin"
PMSET_OWNER = "MeetAutomationScheduledJoin"
SCHEDULE_LAUNCH_AGENT_PATH = (
    Path.home() / "Library/LaunchAgents" / f"{SCHEDULE_LABEL}.plist"
)
SCHEDULE_RUNNER_PATH = BASE_DIR / "run_scheduled_meet.sh"
SCHEDULE_LOG_ROOT = BASE_DIR / "logs"
SCHEDULE_RUNS_DIR = SCHEDULE_LOG_ROOT / "recurring_schedule_runs"
SCHEDULE_LAUNCHD_LOG_DIR = SCHEDULE_LOG_ROOT / "recurring_schedule_launchagent"

WEEKDAY_NAMES = [
    "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
]
WEEKDAY_TO_LAUNCHD = {
    "Sunday": 0, "Monday": 1, "Tuesday": 2, "Wednesday": 3,
    "Thursday": 4, "Friday": 5, "Saturday": 6,
}
WEEKDAY_TO_PMSET = {
    "Monday": "M", "Tuesday": "T", "Wednesday": "W", "Thursday": "R",
    "Friday": "F", "Saturday": "S", "Sunday": "U",
}


@dataclass
class ScheduleConfig:
    meeting_url: str
    chrome_user_data_dir: str
    chrome_profile_directory: str
    chrome_profile_label: str
    weekdays: list[str]
    meeting_time: str
    wake_lead_minutes: int
    timeout_minutes: int
    stay_awake_minutes: int = 60
    launch_agent_label: str = SCHEDULE_LABEL
    pmset_owner: str = PMSET_OWNER


def load_schedule_config(config_path: Path = SCHEDULE_CONFIG_PATH) -> ScheduleConfig | None:
    config_path = Path(config_path)
    if not config_path.exists():
        return None
    with config_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return ScheduleConfig(**data)


def save_schedule_config(
    config: ScheduleConfig,
    config_path: Path = SCHEDULE_CONFIG_PATH,
) -> None:
    with config_path.open("w", encoding="utf-8") as f:
        json.dump(asdict(config), f, indent=2, sort_keys=True)
        f.write("\n")


def applescript_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def prompt_schedule_cancelled(error: RuntimeError) -> None:
    if "-128" in str(error) or "User canceled." in str(error):
        sys.exit("Schedule setup cancelled.")
    raise error


def ask_text(*, title: str, prompt: str, default: str = "") -> str:
    lines = [
        f"set promptText to {applescript_string(prompt)}",
        f"set dialogTitle to {applescript_string(title)}",
        f"set defaultValue to {applescript_string(default)}",
        (
            'set response to display dialog promptText with title '
            'dialogTitle default answer defaultValue buttons '
            '{"Cancel", "✓ Continue"} default button "✓ Continue"'
        ),
        "return text returned of response",
    ]
    try:
        return run_osascript(lines).strip()
    except RuntimeError as error:
        prompt_schedule_cancelled(error)
        raise


def ask_choice(*, title: str, prompt: str, options: list[str], default: str | None = None) -> str:
    options_text = ", ".join(applescript_string(o) for o in options)
    lines = [
        f"set optionList to {{{options_text}}}",
        f"set promptText to {applescript_string(prompt)}",
        f"set dialogTitle to {applescript_string(title)}",
    ]
    if default and default in options:
        lines.append(f"set defaultList to {{{applescript_string(default)}}}")
        default_clause = " default items defaultList"
    else:
        default_clause = ""
    lines.extend(
        [
            (
                "set selectedItems to choose from list optionList "
                "with title dialogTitle with prompt promptText"
                f"{default_clause}"
            ),
            "if selectedItems is false then error number -128",
            "return item 1 of selectedItems",
        ]
    )
    try:
        return run_osascript(lines).strip()
    except RuntimeError as error:
        prompt_schedule_cancelled(error)
        raise


def ask_multi_choice(
    *, title: str, prompt: str, options: list[str], defaults: list[str]
) -> list[str]:
    options_text = ", ".join(applescript_string(o) for o in options)
    default_text = ", ".join(
        applescript_string(o) for o in defaults if o in options
    )
    lines = [
        "on join_lines(item_list)",
        "set AppleScript's text item delimiters to linefeed",
        "set joined_text to item_list as text",
        'set AppleScript\'s text item delimiters to ""',
        "return joined_text",
        "end join_lines",
        f"set optionList to {{{options_text}}}",
        f"set promptText to {applescript_string(prompt)}",
        f"set dialogTitle to {applescript_string(title)}",
    ]
    default_clause = ""
    if default_text:
        lines.append(f"set defaultList to {{{default_text}}}")
        default_clause = " default items defaultList"
    lines.extend(
        [
            (
                "set selectedItems to choose from list optionList "
                "with title dialogTitle with prompt promptText "
                "with multiple selections allowed and empty selection allowed"
                f"{default_clause}"
            ),
            "if selectedItems is false then error number -128",
            "return join_lines(selectedItems)",
        ]
    )
    try:
        result = run_osascript(lines).strip()
    except RuntimeError as error:
        prompt_schedule_cancelled(error)
        raise
    return [item for item in result.splitlines() if item]


def ask_confirmation(*, title: str, prompt: str, confirm_label: str) -> bool:
    confirm_text = applescript_string(confirm_label)
    try:
        result = run_osascript(
            [
                f"set promptText to {applescript_string(prompt)}",
                f"set dialogTitle to {applescript_string(title)}",
                (
                    'set response to display dialog promptText with title '
                    f'dialogTitle buttons {{"Cancel", {confirm_text}}} '
                    f"default button {confirm_text}"
                ),
                "return button returned of response",
            ]
        ).strip()
    except RuntimeError as error:
        prompt_schedule_cancelled(error)
        raise
    return result == confirm_label


def parse_meeting_time(user_input: str) -> str:
    value = " ".join(user_input.strip().split())
    if not value:
        sys.exit("Meeting time cannot be empty.")
    for fmt in ("%I:%M %p", "%I %p", "%H:%M", "%H"):
        try:
            parsed = datetime.strptime(value.upper(), fmt)
            return parsed.strftime("%H:%M")
        except ValueError:
            continue
    sys.exit("Meeting time must look like `10:20 AM`, `10 AM`, or `22:20`.")


def parse_positive_int(
    user_input: str,
    *,
    field_name: str,
    allow_zero: bool = False,
    max_value: int | None = None,
) -> int:
    stripped = user_input.strip()
    if not stripped.isdigit():
        sys.exit(f"{field_name} must be a whole number.")
    value = int(stripped)
    minimum = 0 if allow_zero else 1
    if value < minimum:
        sys.exit(f"{field_name} must be at least {minimum}.")
    if max_value is not None and value > max_value:
        sys.exit(f"{field_name} must be at most {max_value}.")
    return value


def validate_meeting_url(url: str) -> str:
    normalized = url.strip()
    if not normalized:
        sys.exit("Meeting URL cannot be empty.")
    if "meet.google.com" not in normalized:
        sys.exit("Meeting URL must point to Google Meet.")
    return normalized


def collect_schedule_config(
    chrome_user_data_dir: str = str(DEFAULT_CHROME_USER_DATA_DIR),
) -> ScheduleConfig:
    existing = load_schedule_config()
    profiles = list_chrome_profiles(chrome_user_data_dir)
    if not profiles:
        sys.exit("No Chrome profiles found. Open Chrome once and try again.")

    profile_by_label = {p["label"]: p for p in profiles}

    meeting_url = validate_meeting_url(
        ask_text(
            title="Meet Automation",
            prompt="Enter the Google Meet URL for the recurring meeting.",
            default=existing.meeting_url if existing else "",
        )
    )

    default_profile_label = existing.chrome_profile_label if existing else None
    if default_profile_label not in profile_by_label and existing:
        for p in profiles:
            if p["directory"] == existing.chrome_profile_directory:
                default_profile_label = p["label"]
                break

    chosen_label = ask_choice(
        title="Meet Automation",
        prompt="Choose the Chrome profile that should join the meeting.",
        options=[p["label"] for p in profiles],
        default=default_profile_label,
    )
    chosen_profile = profile_by_label[chosen_label]

    selected_weekdays = ask_multi_choice(
        title="Meet Automation",
        prompt="Choose the weekdays for this recurring schedule.",
        options=WEEKDAY_NAMES[1:] + WEEKDAY_NAMES[:1],
        defaults=existing.weekdays if existing else ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
    )
    if not selected_weekdays:
        sys.exit("Pick at least one weekday.")

    default_time = "10:20 AM"
    if existing:
        default_time = (
            datetime.strptime(existing.meeting_time, "%H:%M").strftime("%I:%M %p").lstrip("0")
        )
    meeting_time = parse_meeting_time(
        ask_text(
            title="Meet Automation",
            prompt="Enter the meeting start time (e.g. 10:20 AM, 22:20).",
            default=default_time,
        )
    )

    wake_lead_minutes = parse_positive_int(
        ask_text(
            title="Meet Automation",
            prompt="How many minutes before the meeting should macOS wake up?",
            default=str(existing.wake_lead_minutes) if existing else "1",
        ),
        field_name="Wake lead minutes",
        allow_zero=True,
        max_value=1439,
    )

    timeout_minutes = parse_positive_int(
        ask_text(
            title="Meet Automation",
            prompt="How many minutes should the joiner wait before playing a warning?",
            default=str(existing.timeout_minutes) if existing else "15",
        ),
        field_name="Join timeout minutes",
        max_value=240,
    )

    stay_awake_minutes = parse_positive_int(
        ask_text(
            title="Meet Automation",
            prompt="Minutes to keep the Mac awake after joining (0 to disable).",
            default=str(existing.stay_awake_minutes) if existing else "60",
        ),
        field_name="Stay awake minutes",
        allow_zero=True,
        max_value=1440,
    )

    summary_lines = [
        f"URL: {meeting_url}",
        f"Chrome profile: {chosen_label}",
        f"Days: {', '.join(selected_weekdays)}",
        f"Meeting time: {meeting_time}",
        f"Wake lead: {wake_lead_minutes} minute(s)",
        f"Join timeout: {timeout_minutes} minute(s)",
        f"Stay awake after join: {stay_awake_minutes} minute(s)",
        "",
        "This will install a recurring LaunchAgent and macOS wake schedule.",
    ]
    if not ask_confirmation(
        title="Meet Automation",
        prompt="\n".join(summary_lines),
        confirm_label="✓ Install Schedule",
    ):
        sys.exit("Schedule setup cancelled.")

    return ScheduleConfig(
        meeting_url=meeting_url,
        chrome_user_data_dir=chrome_user_data_dir,
        chrome_profile_directory=chosen_profile["directory"],
        chrome_profile_label=chosen_label,
        weekdays=selected_weekdays,
        meeting_time=meeting_time,
        wake_lead_minutes=wake_lead_minutes,
        timeout_minutes=timeout_minutes,
        stay_awake_minutes=stay_awake_minutes,
    )


def meeting_hour_and_minute(config: ScheduleConfig) -> tuple[int, int]:
    parsed = datetime.strptime(config.meeting_time, "%H:%M")
    return parsed.hour, parsed.minute


def compute_wake_schedule(config: ScheduleConfig) -> tuple[str, str]:
    hour, minute = meeting_hour_and_minute(config)
    base = datetime(2024, 1, 1, hour, minute)
    wake_dt = base - timedelta(minutes=config.wake_lead_minutes)
    wake_time = wake_dt.strftime("%H:%M:%S")

    meeting_index_to_name = {
        1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday",
        5: "Friday", 6: "Saturday", 7: "Sunday",
    }
    shifted_days: list[str] = []
    day_offset = (wake_dt.date() - base.date()).days

    for weekday_name in config.weekdays:
        meeting_weekday = WEEKDAY_TO_LAUNCHD[weekday_name]
        normalized = 7 if meeting_weekday == 0 else meeting_weekday
        shifted = ((normalized - 1 + day_offset) % 7) + 1
        shifted_days.append(meeting_index_to_name[shifted])

    pmset_day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    pmset_days = "".join(
        WEEKDAY_TO_PMSET[d] for d in pmset_day_order if d in shifted_days
    )
    return pmset_days, wake_time


def create_launch_agent_payload(config: ScheduleConfig) -> dict:
    hour, minute = meeting_hour_and_minute(config)
    intervals = [
        {"Weekday": WEEKDAY_TO_LAUNCHD[d], "Hour": hour, "Minute": minute}
        for d in config.weekdays
    ]
    return {
        "Label": config.launch_agent_label,
        "ProgramArguments": [
            "/bin/zsh",
            str(SCHEDULE_RUNNER_PATH),
            "--config",
            str(SCHEDULE_CONFIG_PATH),
        ],
        "WorkingDirectory": str(BASE_DIR),
        "StartCalendarInterval": intervals,
        "ProcessType": "Interactive",
        "EnvironmentVariables": {
            "HOME": str(Path.home()),
            "PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            "PYTHONUNBUFFERED": "1",
        },
        "StandardOutPath": str(SCHEDULE_LAUNCHD_LOG_DIR / "launchd_stdout.log"),
        "StandardErrorPath": str(SCHEDULE_LAUNCHD_LOG_DIR / "launchd_stderr.log"),
    }


def os_uid() -> int:
    return int(subprocess.check_output(["id", "-u"], text=True).strip())


def ensure_schedule_log_dirs() -> None:
    SCHEDULE_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    SCHEDULE_LAUNCHD_LOG_DIR.mkdir(parents=True, exist_ok=True)


def install_launch_agent(config: ScheduleConfig) -> None:
    payload = create_launch_agent_payload(config)
    SCHEDULE_LAUNCH_AGENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ensure_schedule_log_dirs()

    if SCHEDULE_LAUNCH_AGENT_PATH.exists():
        subprocess.run(
            ["launchctl", "bootout", f"gui/{os_uid()}", str(SCHEDULE_LAUNCH_AGENT_PATH)],
            check=False,
        )

    with SCHEDULE_LAUNCH_AGENT_PATH.open("wb") as f:
        plistlib.dump(payload, f, sort_keys=False)

    subprocess.run(["plutil", "-lint", str(SCHEDULE_LAUNCH_AGENT_PATH)], check=True)
    subprocess.run(
        ["launchctl", "bootstrap", f"gui/{os_uid()}", str(SCHEDULE_LAUNCH_AGENT_PATH)],
        check=True,
    )


def remove_launch_agent() -> None:
    if SCHEDULE_LAUNCH_AGENT_PATH.exists():
        subprocess.run(
            ["launchctl", "bootout", f"gui/{os_uid()}", str(SCHEDULE_LAUNCH_AGENT_PATH)],
            check=False,
        )
        SCHEDULE_LAUNCH_AGENT_PATH.unlink()


def install_pmset_repeat(config: ScheduleConfig) -> None:
    pmset_days, wake_time = compute_wake_schedule(config)
    print("Installing the recurring macOS wake schedule. You may be prompted for your password.")
    subprocess.run(
        ["sudo", "/usr/bin/pmset", "repeat", "wakeorpoweron", pmset_days, wake_time],
        check=True,
    )


def run_pmset_repeat_cancel() -> None:
    print("Clearing the repeating wake schedule. You may be prompted for your password.")
    subprocess.run(["sudo", "/usr/bin/pmset", "repeat", "cancel"], check=True)


def schedule_recurring_meet() -> None:
    config = collect_schedule_config()
    ensure_schedule_log_dirs()
    save_schedule_config(config)

    log_phase("schedule", "Installing LaunchAgent and macOS wake schedule.")
    install_launch_agent(config)
    run_pmset_repeat_cancel()
    install_pmset_repeat(config)
    subprocess.run(["/usr/bin/pmset", "-g", "sched"], check=False)

    log_phase("schedule", "Recurring schedule installed successfully.")
    print()
    print(f"Config saved to:        {SCHEDULE_CONFIG_PATH}")
    print(f"LaunchAgent installed:  {SCHEDULE_LAUNCH_AGENT_PATH}")
    print(f"Scheduled runs dir:     {SCHEDULE_RUNS_DIR}")


def unschedule_recurring_meet() -> None:
    log_phase("schedule", "Removing LaunchAgent and macOS wake schedule.")
    remove_launch_agent()
    run_pmset_repeat_cancel()
    if SCHEDULE_CONFIG_PATH.exists():
        SCHEDULE_CONFIG_PATH.unlink()
    print()
    print("Recurring schedule removed.")
    print(f"LaunchAgent cleared:  {SCHEDULE_LAUNCH_AGENT_PATH}")
    print(f"Config removed:       {SCHEDULE_CONFIG_PATH}")


def run_scheduled_job(config_path: Path) -> None:
    config = load_schedule_config(config_path)
    if config is None:
        sys.exit(f"Schedule config not found: {config_path}")

    log_phase("schedule-config", f"Loaded config from {config_path}.")

    subprocess.run(["/usr/bin/caffeinate", "-u", "-t", "5"], check=False)

    network_ready = False
    for attempt in range(1, 31):
        state = subprocess.run(
            ["/usr/sbin/scutil", "-r", "meet.google.com"],
            capture_output=True,
            text=True,
            check=False,
        )
        output = (state.stdout or "") + (state.stderr or "")
        if "Reachable" in output:
            network_ready = True
            log_phase("network", f"Network reachable after attempt {attempt}.")
            break
        log_phase("network", f"Network unavailable on attempt {attempt}. Retrying.")
        time.sleep(2)

    if not network_ready:
        sys.exit("Network did not become reachable within 60 seconds.")

    log_phase("meet-handoff", "Handing off to the Meet joiner.")


def build_run_command(config: ScheduleConfig) -> list[str]:
    return [
        sys.executable,
        str(BASE_DIR / "meet_automation.py"),
        "run",
        "--url",
        config.meeting_url,
        "--chrome-user-data-dir",
        config.chrome_user_data_dir,
        "--chrome-profile-directory",
        config.chrome_profile_directory,
        "--timeout-minutes",
        str(config.timeout_minutes),
        "--stay-awake-minutes",
        str(config.stay_awake_minutes),
    ]


def execute_scheduled_meet_run(config_path: Path) -> int:
    config = load_schedule_config(Path(config_path))
    if config is None:
        log_phase("schedule-config", f"Missing config at {config_path}.")
        return 1

    run_scheduled_job(Path(config_path))
    command = build_run_command(config)
    log_phase(
        "meet-handoff",
        "Executing: " + " ".join(shlex.quote(part) for part in command),
    )
    result = subprocess.run(command, check=False)
    return result.returncode
