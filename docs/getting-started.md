# Getting Started

## Requirements

- macOS (tested on macOS 14+)
- Python 3.11+
- Google Chrome installed at `/Applications/Google Chrome.app`
- A Google account signed into a Chrome profile

## Setup

### 1. Clone and create a virtual environment

```sh
git clone <repo-url>
cd meet-automation-community
python3 -m venv .venv
source .venv/bin/activate
```

No third-party packages are required. The tool uses only the Python standard library.

If virtualenv creation is interrupted and `.venv` is left in a partial state, rebuild it with:

```sh
python3 -m venv --clear .venv
source .venv/bin/activate
```

### 2. Enable JavaScript from Apple Events in Chrome

Open Chrome, then:

```
View > Developer > Allow JavaScript from Apple Events
```

This is required for the AppleScript automation bridge. The setting persists across restarts.

### 3. Sign in with the correct Google account

Run `setup` to open Chrome in the automation profile and confirm the right account is signed in:

```sh
python meet_automation.py setup --chrome-profile-name "Your Name"
```

Replace `"Your Name"` with the display name or email of the Chrome profile you want to use. Alternatively, use `--chrome-profile-directory` if you know the profile folder name (e.g. `Profile 1`).

Follow the on-screen instructions to sign in, then press Enter.

### 4. Run a one-off join

```sh
python meet_automation.py run \
  --url "https://meet.google.com/abc-defg-hij" \
  --chrome-profile-name "Your Name" \
  --timeout-minutes 15 \
  --stay-awake-minutes 60
```

- `--timeout-minutes`: how long to wait in the waiting room before playing a voice warning
- `--stay-awake-minutes`: how long to hold the session after being admitted (0 to exit immediately)

Screenshots are saved to `logs/` automatically.

### 5. Set up a recurring schedule

```sh
python meet_automation.py schedule
```

A series of macOS dialog prompts will collect:
- The meeting URL
- The Chrome profile to use
- The weekdays and time
- Wake-up lead time before the meeting
- Admission timeout and post-join hold duration

Two system-level changes are made (both require `sudo` for the pmset step):
- A **LaunchAgent** is installed at `~/Library/LaunchAgents/com.user.meet.scheduledjoin.plist`
- A **pmset** wake schedule is set so the Mac wakes up before the meeting

### 6. Remove the schedule

```sh
python meet_automation.py unschedule
```

This removes the LaunchAgent and clears the pmset wake schedule.

## Logs and screenshots

All logs and screenshots are written to `logs/` relative to the project directory (or `$MEET_AUTOMATION_LOG_DIR` if set). Each scheduled run gets its own subdirectory under `logs/recurring_schedule_runs/`.

## Quick smoke test

Before publishing or sharing the repo, you can run this lightweight validation:

```sh
./.venv/bin/python --version
./.venv/bin/python -m pip --version
./.venv/bin/python -m compileall meet_automation.py browser common scheduler
./.venv/bin/python meet_automation.py --help
./.venv/bin/python meet_automation.py setup --help
./.venv/bin/python meet_automation.py run --help
./.venv/bin/python meet_automation.py schedule --help
./.venv/bin/python meet_automation.py unschedule --help
```

## Troubleshooting

**"Executing JavaScript through AppleScript is turned off"**
Enable `View > Developer > Allow JavaScript from Apple Events` in Chrome.

**"No Chrome profiles found"**
Open Chrome once and let it create a profile, then retry.

**Google redirects to sign-in**
The account in the selected Chrome profile may not be signed in. Run `setup` again.
