# Architecture

Meet Automation Community Edition is a macOS-native, headless-free automation system. It uses the real signed-in Chrome session rather than a browser-control framework, which means no Selenium, no Playwright, and no CDP — just AppleScript talking to the live Chrome window.

## Key design decisions

### Live Chrome over headless

Google Meet actively detects and blocks headless browsers. This tool opens an actual Chrome window with an existing signed-in profile, navigates to the meeting URL, and drives the DOM via AppleScript JavaScript injection (`Allow JavaScript from Apple Events`). The result is indistinguishable from a human-operated session.

### Phase-based execution

Each run progresses through named phases logged in real time:

| Phase | Description |
|---|---|
| `profile` | Chrome launches with the selected user-data-dir and profile-directory |
| `load` | Meeting URL opens; page stabilizes |
| `identity` | Signed-in vs guest join flow is detected |
| `media` | Microphone and camera are turned off before joining |
| `join-click` | The Ask to join / Join now button is located and clicked |
| `admission` | The loop polls for host admission or a waiting-room state |
| `connected` | Post-join hold window keeps the session alive (optional) |

Screenshots are saved at each key phase transition into the `logs/` directory.

### macOS scheduler architecture

```
pmset repeat wakeorpoweron   ←── wakes the Mac N minutes before the meeting
        │
        └── LaunchAgent (launchd)   ←── fires at the meeting time via StartCalendarInterval
                │
                └── run_scheduled_meet.sh   ←── shell wrapper; sets up LOG_DIR, checks venv
                        │
                        └── meet_automation.py run-scheduled-job   ←── waits for network, then runs
                                │
                                └── browser/basic_chrome.py   ←── the join flow
```

The two-layer wake approach (pmset + launchd) is required because launchd alone cannot wake a sleeping Mac — it only fires if the Mac is already awake. `pmset repeat wakeorpoweron` handles the wake, and launchd handles the timed execution.

## Module layout

```
meet_automation.py        — CLI entrypoint (setup / run / schedule / unschedule)
browser/
  basic_chrome.py         — Chrome launch, AppleScript JS bridge, join flow
scheduler/
  schedule.py             — ScheduleConfig, LaunchAgent plist builder, pmset management
common/
  config.py               — BASE_DIR, Chrome profile discovery and resolution
  logging_utils.py        — log(), log_phase(), screenshots, caffeinate, osascript runner
run_scheduled_meet.sh     — Shell wrapper invoked by launchd
```

## What this edition does not include

This community edition is a reference implementation. The production reliability layer — layered DOM fallback strategies, adaptive join-click retry tuning, advanced state classification, and AppleScript edge case handling developed through repeated real-world sessions — is not part of this release.

The public runner intentionally keeps the DOM strategy small:

- direct `button` lookups for `Ask to join` / `Join now`
- basic `aria-label` checks for microphone and camera toggles
- straightforward waiting-room polling and post-join hold behavior

That keeps the repo credible and usable without publishing the full private reliability engine.
