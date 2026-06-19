#!/usr/bin/env python3

import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

from common.config import BASE_DIR

LOG_DIR_ENV_VAR = "MEET_AUTOMATION_LOG_DIR"


def resolve_log_dir() -> Path:
    configured = os.environ.get(LOG_DIR_ENV_VAR, "logs").strip() or "logs"
    candidate = Path(configured).expanduser()
    if not candidate.is_absolute():
        candidate = BASE_DIR / candidate
    return candidate.resolve()


LOG_DIR = resolve_log_dir()
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "meet_automation.log"


def log(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {message}"
    print(formatted, flush=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(formatted + "\n")


def log_phase(phase: str, message: str) -> None:
    log(f"[{phase}] {message}")


def save_chrome_screenshot(name: str) -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = LOG_DIR / f"{timestamp}_{name}.png"
    try:
        subprocess.run(["screencapture", "-x", str(path)], check=True)
        log(f"Screenshot saved: {path}")
    except Exception as error:
        log(f"Could not save screenshot: {error}")


def play_warning() -> None:
    log("Admission timeout reached. Playing warning.")
    warning_text = "Google Meet has not admitted you. Please check the meeting."
    for _ in range(3):
        try:
            subprocess.run(["say", warning_text], check=False)
        except Exception as error:
            log(f"Unable to play voice warning: {error}")
        time.sleep(2)


def run_osascript(lines: list[str]) -> str:
    command = ["osascript"]
    for line in lines:
        command.extend(["-e", line])

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(stderr or "AppleScript command failed.")

    return result.stdout.strip()


def start_caffeinate() -> subprocess.Popen:
    return subprocess.Popen(
        ["caffeinate", "-i", "-w", str(os.getpid())],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def start_post_join_caffeinate(minutes: int) -> subprocess.Popen | None:
    if minutes <= 0:
        return None
    log(f"Starting post-join caffeinate hold for {minutes} minute(s).")
    return subprocess.Popen(
        ["caffeinate", "-dimsu", "-t", str(minutes * 60)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def terminate_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
