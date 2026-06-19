# Meet Automation Community Edition

Unattended Google Meet joining on macOS — no headless browser, no Selenium, no paid services.

This tool opens a real signed-in Chrome session, navigates to a Google Meet URL, and clicks Ask to join on your behalf. It integrates with macOS scheduling so the Mac wakes up and joins the meeting automatically at a configured time each week.

> **Community Edition disclaimer:** This is a reference implementation that demonstrates the architecture and core join flow. It is intentionally simpler than the full production reliability engine. The layered DOM fallback strategies, adaptive retry tuning, and advanced state classification developed through extended real-world use are not part of this release.

## What it does

- Opens Chrome with a specific Google profile (no new account required)
- Navigates to a Google Meet URL and waits for the pre-join screen
- Turns off the microphone and camera before joining
- Clicks Ask to join and polls for host admission
- Saves screenshots at each phase transition (`logs/`)
- Plays a macOS voice warning if admission times out
- Optionally holds the session open for a configured duration after joining
- Integrates with macOS LaunchAgents and `pmset` for fully unattended recurring scheduling

## Supported platform

macOS only. Requires Google Chrome installed at `/Applications/Google Chrome.app`.

## Quick start

```sh
# 1. Create a virtual environment (no extra packages needed)
python3 -m venv .venv && source .venv/bin/activate

# 2. Enable JavaScript from Apple Events in Chrome:
#    View > Developer > Allow JavaScript from Apple Events

# 3. Sign in with the correct Google account
python meet_automation.py setup --chrome-profile-name "Your Name"

# 4. Join a meeting
python meet_automation.py run \
  --url "https://meet.google.com/abc-defg-hij" \
  --chrome-profile-name "Your Name" \
  --timeout-minutes 15 \
  --stay-awake-minutes 60

# 5. Set up a recurring weekly schedule (interactive prompts)
python meet_automation.py schedule

# 6. Remove the schedule
python meet_automation.py unschedule
```

## CLI reference

```
meet_automation.py setup        Open Chrome for Google sign-in
meet_automation.py run          Join a meeting by URL
meet_automation.py schedule     Install a recurring LaunchAgent + pmset wake schedule
meet_automation.py unschedule   Remove the recurring schedule
```

Run any subcommand with `--help` for full options.

## Architecture

```
meet_automation.py            CLI entrypoint
browser/basic_chrome.py       Chrome launch + AppleScript JS bridge + join flow
scheduler/schedule.py         ScheduleConfig, LaunchAgent plist builder, pmset
common/config.py              Chrome profile discovery and path resolution
common/logging_utils.py       Logging, screenshots, caffeinate, osascript runner
run_scheduled_meet.sh         Shell wrapper invoked by launchd at meeting time
```

The automation uses AppleScript to inject JavaScript into the live Chrome tab — no Playwright, no ChromeDriver, no CDP. See [docs/architecture.md](docs/architecture.md) for a full breakdown.

## Scheduling

The recurring schedule uses two macOS mechanisms working together:

1. **`pmset repeat wakeorpoweron`** — wakes the Mac N minutes before the meeting
2. **LaunchAgent (`StartCalendarInterval`)** — fires the joiner at the meeting time

See [docs/scheduling.md](docs/scheduling.md) for the full design.

## Proof

The [proof/](proof/) folder contains a sanitized log excerpt showing a complete end-to-end scheduled run from network-readiness check through admission and post-join hold.

## Docs

- [Getting started](docs/getting-started.md)
- [Architecture](docs/architecture.md)
- [Scheduling deep dive](docs/scheduling.md)

## License

MIT — see [LICENSE](LICENSE).
