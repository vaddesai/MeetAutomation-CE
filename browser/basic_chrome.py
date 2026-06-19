#!/usr/bin/env python3

import json
import subprocess
import time

from common.config import chrome_executable
from common.logging_utils import (
    log,
    log_phase,
    play_warning,
    run_osascript,
    save_chrome_screenshot,
    start_caffeinate,
    start_post_join_caffeinate,
    terminate_process,
)


def launch_chrome(
    user_data_dir: str,
    profile_directory: str,
    url: str,
) -> subprocess.Popen:
    return subprocess.Popen(
        [
            chrome_executable(),
            f"--user-data-dir={user_data_dir}",
            f"--profile-directory={profile_directory}",
            "--new-window",
            url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def setup_chrome_profile(
    chrome_user_data_dir: str,
    chrome_profile_directory: str,
) -> None:
    log("Opening the automation Chrome profile for sign-in.")
    process = launch_chrome(
        chrome_user_data_dir,
        chrome_profile_directory,
        "about:blank",
    )
    try:
        print()
        print("Complete these steps in the Chrome window:")
        print("1. Sign in with the Google account used for the meeting.")
        print("2. Confirm the account is visible at accounts.google.com.")
        print("3. Close the Chrome window and return here.")
        print()
        input("Press Enter after sign-in is complete: ")
    finally:
        terminate_process(process)
    log("Chrome profile setup completed.")


def open_meet_url(meet_url: str) -> None:
    run_osascript(
        [
            'tell application "Google Chrome" to activate',
            (
                'tell application "Google Chrome" to if (count of windows) = 0 '
                'then make new window'
            ),
            (
                'tell application "Google Chrome" to make new tab at end of '
                f'tabs of front window with properties {{URL:"{meet_url}"}}'
            ),
            (
                'tell application "Google Chrome" to set active tab index of '
                'front window to (count of tabs of front window)'
            ),
        ]
    )


def execute_js(script: str) -> str:
    escaped = script.replace("\\", "\\\\").replace('"', '\\"')
    return run_osascript(
        [
            (
                'tell application "Google Chrome" to execute active tab of '
                f'front window javascript "{escaped}"'
            )
        ]
    )


def collect_page_state() -> dict:
    result = execute_js(
        """
        (() => {
            const text = document.body ? document.body.innerText.slice(0, 4000) : "";
            const buttons = Array.from(document.querySelectorAll("button"));
            const joinButton = buttons.find((b) => {
                const t = (b.innerText || "").trim().toLowerCase();
                const rect = b.getBoundingClientRect();
                return (t === "ask to join" || t === "join now") && rect.width > 0;
            });
            return JSON.stringify({
                href: document.location.href,
                text: text,
                joinButtonVisible: !!joinButton,
                guestPrompt: !!document.querySelector('input[placeholder="Your name"]'),
            });
        })()
        """
    )
    return json.loads(result) if result else {}


def click_join_button() -> bool:
    result = execute_js(
        """
        (() => {
            const buttons = Array.from(document.querySelectorAll("button"));
            const target = buttons.find((b) => {
                const t = (b.innerText || "").trim().toLowerCase();
                const rect = b.getBoundingClientRect();
                return (t === "ask to join" || t === "join now") && rect.width > 0;
            });
            if (target) {
                target.click();
                return "clicked";
            }
            return "missing";
        })()
        """
    )
    return result == "clicked"


def fill_guest_name(display_name: str) -> None:
    safe_display_name = json.dumps(display_name)
    execute_js(
        f"""
        (() => {{
            const field = document.querySelector('input[placeholder="Your name"]');
            if (!field || (field.value || "").trim()) return;
            field.focus();
            field.value = {safe_display_name};
            field.dispatchEvent(new Event("input", {{ bubbles: true }}));
            field.dispatchEvent(new Event("change", {{ bubbles: true }}));
        }})()
        """
    )


def turn_off_media() -> None:
    for device in ("microphone", "camera"):
        result = execute_js(
            f"""
            (() => {{
                const el = Array.from(
                    document.querySelectorAll("button, [role='button']")
                ).find((b) => {{
                    const label = (b.getAttribute("aria-label") || "").toLowerCase();
                    const rect = b.getBoundingClientRect();
                    return (
                        label.includes("{device}") &&
                        label.includes("turn off") &&
                        rect.width > 0
                    );
                }});
                if (!el) return "missing";
                el.click();
                return "clicked";
            }})()
            """
        )
        if result == "clicked":
            log_phase("media", f"Turned {device} off.")


def is_admitted(state: dict) -> bool:
    text = state.get("text", "").lower()
    has_leave = "leave call" in text or "end call" in text
    return has_leave and not state.get("joinButtonVisible", False)


def is_waiting_for_host(state: dict) -> bool:
    return (
        "please wait until a meeting host brings you into the call"
        in state.get("text", "").lower()
    )


def run_meeting_with_live_chrome(
    meet_url: str,
    timeout_minutes: int,
    display_name: str,
    chrome_user_data_dir: str,
    chrome_profile_directory: str,
    stay_awake_minutes: int = 0,
) -> None:
    caffeinate = start_caffeinate()
    post_join_caffeinate = None

    try:
        log_phase(
            "profile",
            f"Launching Chrome with profile `{chrome_profile_directory}`.",
        )
        launch_chrome(chrome_user_data_dir, chrome_profile_directory, meet_url)
        time.sleep(5)

        log_phase("load", f"Opening: {meet_url}")
        time.sleep(8)
        save_chrome_screenshot("meet_opened")

        state = collect_page_state()
        page_text = state.get("text", "")
        page_url = state.get("href", "")

        if "accounts.google.com" in page_url or "sign in" in page_text.lower():
            log_phase("auth", "Failure: Google requested sign-in.")
            save_chrome_screenshot("login_required")
            play_warning()
            return

        if any(
            phrase in page_text.lower()
            for phrase in (
                "you can't join this video call",
                "this call has ended",
                "meeting code not found",
            )
        ):
            log_phase("access", "Failure: Google Meet blocked the join.")
            save_chrome_screenshot("join_blocked")
            play_warning()
            return

        if state.get("guestPrompt"):
            log_phase("identity", "Guest join flow detected. Filling display name.")
            fill_guest_name(display_name)
        else:
            log_phase("identity", "Signed-in join flow detected.")

        turn_off_media()
        save_chrome_screenshot("prejoin_ready")

        if not click_join_button():
            log_phase("join-click", "Failure: Could not find the join button.")
            save_chrome_screenshot("join_button_missing")
            play_warning()
            return

        log_phase("join-click", "Clicked the join button. Waiting for admission.")
        save_chrome_screenshot("join_requested")

        deadline = time.time() + timeout_minutes * 60
        warned = False
        waiting_screenshot_saved = False

        while True:
            state = collect_page_state()

            if is_admitted(state):
                log_phase("admission", "Success: admitted into the meeting.")
                save_chrome_screenshot("admitted")
                post_join_caffeinate = start_post_join_caffeinate(stay_awake_minutes)
                if stay_awake_minutes > 0:
                    log_phase(
                        "connected",
                        f"Holding the session for {stay_awake_minutes} minute(s).",
                    )
                    time.sleep(stay_awake_minutes * 60)
                break

            if is_waiting_for_host(state):
                if not waiting_screenshot_saved:
                    save_chrome_screenshot("waiting_for_host")
                    waiting_screenshot_saved = True
                log_phase("admission", "Waiting for the host to admit the account.")
                time.sleep(5)
                continue

            if time.time() >= deadline and not warned:
                save_chrome_screenshot("admission_timeout")
                play_warning()
                warned = True

            log_phase("admission", "Waiting to be admitted.")
            time.sleep(5)

    except Exception as error:
        if "Executing JavaScript through AppleScript is turned off" in str(error):
            log(
                "JavaScript via AppleScript is disabled. Enable "
                "`View > Developer > Allow JavaScript from Apple Events` "
                "in Google Chrome and rerun."
            )
        log(f"Automation error: {error}")
        play_warning()

    finally:
        terminate_process(post_join_caffeinate)
        caffeinate.terminate()
