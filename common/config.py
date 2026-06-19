#!/usr/bin/env python3

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_CHROME_USER_DATA_DIR = (
    Path.home() / "Library/Application Support/Google/Chrome"
)


def chrome_executable() -> str:
    chrome_path = Path(
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    )
    if chrome_path.exists():
        return str(chrome_path)
    sys.exit(
        f"Google Chrome not found at {chrome_path}. Install Chrome or update the path."
    )


def chrome_profile_exists(user_data_dir: str, profile_directory: str) -> bool:
    return (Path(user_data_dir) / profile_directory).exists()


def find_chrome_profile_directory_by_name(
    user_data_dir: str,
    profile_name: str,
) -> str | None:
    local_state_path = Path(user_data_dir) / "Local State"
    if not local_state_path.exists():
        return None

    try:
        with local_state_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except Exception:
        return None

    info_cache = data.get("profile", {}).get("info_cache", {})
    wanted = profile_name.strip().casefold()
    if not wanted:
        return None

    for directory, metadata in info_cache.items():
        for field_name in ("name", "gaia_name", "user_name", "gaia_given_name"):
            value = str(metadata.get(field_name, "")).strip()
            if value and value.casefold() == wanted:
                return directory

    return None


def list_chrome_profiles(user_data_dir: str) -> list[dict[str, str]]:
    local_state_path = Path(user_data_dir) / "Local State"
    if not local_state_path.exists():
        return []

    try:
        with local_state_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except Exception:
        return []

    info_cache = data.get("profile", {}).get("info_cache", {})
    profiles: list[dict[str, str]] = []

    for directory, metadata in info_cache.items():
        if not chrome_profile_exists(user_data_dir, directory):
            continue

        short_name = str(metadata.get("name", "")).strip()
        full_name = str(metadata.get("gaia_name", "")).strip()
        account_name = str(metadata.get("user_name", "")).strip()

        parts = [p for p in (short_name, full_name, account_name) if p]
        if not parts:
            parts = [directory]

        label = " | ".join(parts) + f" [{directory}]"
        profiles.append(
            {
                "directory": directory,
                "label": label,
                "short_name": short_name,
                "full_name": full_name,
                "account_name": account_name,
            }
        )

    profiles.sort(
        key=lambda p: (
            p["short_name"].casefold(),
            p["full_name"].casefold(),
            p["directory"].casefold(),
        )
    )
    return profiles


def resolve_explicit_chrome_profile_directory(
    user_data_dir: str,
    profile_directory: str | None = None,
    profile_name: str | None = None,
) -> str:
    if profile_directory:
        if chrome_profile_exists(user_data_dir, profile_directory):
            return profile_directory
        sys.exit(
            f"Chrome profile directory not found: {profile_directory}"
        )

    if profile_name:
        resolved = find_chrome_profile_directory_by_name(
            user_data_dir=user_data_dir,
            profile_name=profile_name,
        )
        if resolved is not None:
            return resolved
        sys.exit(
            f"No Chrome profile matched the name: {profile_name}"
        )

    sys.exit(
        "Pass --chrome-profile-directory or --chrome-profile-name to select a profile."
    )
