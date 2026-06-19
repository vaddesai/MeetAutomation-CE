# Proof Artifacts

This folder contains sanitized evidence of end-to-end runs.

## What each artifact demonstrates

### `sample_log_excerpt.txt`

A redacted log excerpt from a successful scheduled run. It shows the full phase sequence:

- `profile` — Chrome launches with the correct profile
- `load` — Meet URL is opened and the page stabilizes
- `identity` — The signed-in account is detected (no guest flow needed)
- `media` — The runner attempts to turn microphone and camera off before joining
- `join-click` — The Ask to join button is located and clicked
- `admission` — The tool polls the page until the host admits the account
- `connected` — Post-join hold window runs for the configured duration

### Screenshots (not included in this repo)

Screenshots are saved locally during each run at key phase transitions:
`meet_opened`, `prejoin_ready`, `join_requested`, `waiting_for_host`, `admitted`.

These are not included here because they contain on-screen account context. Redacted versions may be added in a future release.

## What is not included

- Full log histories
- Raw `logs/` directory contents
- Schedule config files with real URLs or profile paths
- Account emails, profile names, or machine-specific identifiers
