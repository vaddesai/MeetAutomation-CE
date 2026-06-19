# Scheduling Deep Dive

## How the two-layer wake schedule works

macOS launchd (`StartCalendarInterval`) fires jobs at a specific time — but only if the Mac is already awake. If the machine is asleep, the job is silently skipped.

To guarantee the Mac is awake at meeting time, this tool uses two complementary mechanisms:

1. **`pmset repeat wakeorpoweron`** — instructs macOS power management to physically wake the machine N minutes before the meeting. This fires even from deep sleep.

2. **LaunchAgent (`StartCalendarInterval`)** — fires the automation script at the exact meeting time, after the Mac is already awake.

The `wake_lead_minutes` setting controls the offset. A value of `1` wakes the Mac one minute before the meeting. The pmset schedule accounts for this offset automatically — if the meeting is at 10:20 AM and the lead is 1 minute, pmset is set for 10:19 AM.

## LaunchAgent plist structure

The generated plist at `~/Library/LaunchAgents/com.user.meet.scheduledjoin.plist` looks like:

```xml
<key>ProgramArguments</key>
<array>
    <string>/bin/zsh</string>
    <string>/path/to/run_scheduled_meet.sh</string>
    <string>--config</string>
    <string>/path/to/.meet_automation_schedule.json</string>
</array>
<key>StartCalendarInterval</key>
<array>
    <dict>
        <key>Weekday</key><integer>1</integer>
        <key>Hour</key><integer>10</integer>
        <key>Minute</key><integer>20</integer>
    </dict>
</array>
```

`Weekday` uses the launchd convention: 0 = Sunday, 1 = Monday, ..., 6 = Saturday.

## The schedule config file

The config is stored at `.meet_automation_schedule.json` in the project directory:

```json
{
  "chrome_profile_directory": "Profile 1",
  "chrome_profile_label": "Work Account [Profile 1]",
  "chrome_user_data_dir": "/Users/you/Library/Application Support/Google/Chrome",
  "launch_agent_label": "com.user.meet.scheduledjoin",
  "meeting_time": "10:20",
  "meeting_url": "https://meet.google.com/abc-defg-hij",
  "pmset_owner": "MeetAutomationScheduledJoin",
  "stay_awake_minutes": 60,
  "timeout_minutes": 15,
  "wake_lead_minutes": 1,
  "weekdays": ["Monday", "Wednesday", "Friday"]
}
```

This file is gitignored and machine-specific. Do not commit it.

## Network readiness check

After waking from sleep, the network may not be immediately available. The scheduler waits up to 60 seconds (30 attempts × 2 second intervals) for `meet.google.com` to become reachable via `scutil -r` before handing off to the joiner. If the network does not come up in time, the run exits with an error.

## Inspecting launchctl state

To check whether the LaunchAgent is loaded:

```sh
launchctl list | grep com.user.meet
```

To view the last exit code and run time:

```sh
launchctl print gui/$(id -u)/com.user.meet.scheduledjoin
```

To manually trigger the agent (for testing):

```sh
launchctl kickstart -k gui/$(id -u)/com.user.meet.scheduledjoin
```
