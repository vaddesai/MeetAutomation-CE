#!/usr/bin/env python3

import argparse
import sys

from browser.basic_chrome import run_meeting_with_live_chrome, setup_chrome_profile
from common.config import DEFAULT_CHROME_USER_DATA_DIR, resolve_explicit_chrome_profile_directory
from scheduler.schedule import (
    SCHEDULE_CONFIG_PATH,
    execute_scheduled_meet_run,
    schedule_recurring_meet,
    unschedule_recurring_meet,
)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Meet Automation Community Edition — unattended Google Meet joining"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup_parser = subparsers.add_parser(
        "setup",
        help="Open Chrome with the selected profile for Google sign-in",
    )
    setup_parser.add_argument(
        "--chrome-user-data-dir",
        default=str(DEFAULT_CHROME_USER_DATA_DIR),
        help="Chrome user data directory",
    )
    setup_parser.add_argument(
        "--chrome-profile-directory",
        help="Explicit Chrome profile directory name (e.g. 'Profile 1')",
    )
    setup_parser.add_argument(
        "--chrome-profile-name",
        help="Chrome profile display name or Google account name to resolve",
    )

    run_parser = subparsers.add_parser(
        "run",
        help="Open a meeting and click Ask to join",
    )
    run_parser.add_argument("--url", required=True, help="Google Meet URL")
    run_parser.add_argument(
        "--timeout-minutes",
        type=int,
        default=15,
        help="Minutes to wait for admission before playing a warning (default: 15)",
    )
    run_parser.add_argument(
        "--display-name",
        default="Meet Automation",
        help="Guest display name if Meet asks for one (default: Meet Automation)",
    )
    run_parser.add_argument(
        "--stay-awake-minutes",
        type=int,
        default=0,
        help="Minutes to hold the session open after a successful join (default: 0)",
    )
    run_parser.add_argument(
        "--chrome-user-data-dir",
        default=str(DEFAULT_CHROME_USER_DATA_DIR),
        help="Chrome user data directory",
    )
    run_parser.add_argument(
        "--chrome-profile-directory",
        help="Explicit Chrome profile directory name",
    )
    run_parser.add_argument(
        "--chrome-profile-name",
        help="Chrome profile display name or account name to resolve",
    )

    subparsers.add_parser(
        "schedule",
        help="Create or replace the recurring macOS wake + LaunchAgent schedule",
    )
    subparsers.add_parser(
        "unschedule",
        help="Remove the recurring macOS wake + LaunchAgent schedule",
    )

    scheduled_run_parser = subparsers.add_parser(
        "run-scheduled-job",
        help="Internal entrypoint invoked by the LaunchAgent",
    )
    scheduled_run_parser.add_argument(
        "--config",
        default=str(SCHEDULE_CONFIG_PATH),
        help="Path to the recurring schedule config",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    if args.command == "setup":
        profile_dir = resolve_explicit_chrome_profile_directory(
            user_data_dir=args.chrome_user_data_dir,
            profile_directory=args.chrome_profile_directory,
            profile_name=args.chrome_profile_name,
        )
        setup_chrome_profile(
            chrome_user_data_dir=args.chrome_user_data_dir,
            chrome_profile_directory=profile_dir,
        )
        return

    if args.command == "run":
        profile_dir = resolve_explicit_chrome_profile_directory(
            user_data_dir=args.chrome_user_data_dir,
            profile_directory=args.chrome_profile_directory,
            profile_name=args.chrome_profile_name,
        )
        run_meeting_with_live_chrome(
            meet_url=args.url,
            timeout_minutes=args.timeout_minutes,
            display_name=args.display_name,
            chrome_user_data_dir=args.chrome_user_data_dir,
            chrome_profile_directory=profile_dir,
            stay_awake_minutes=args.stay_awake_minutes,
        )
        return

    if args.command == "schedule":
        schedule_recurring_meet()
        return

    if args.command == "unschedule":
        unschedule_recurring_meet()
        return

    if args.command == "run-scheduled-job":
        raise SystemExit(execute_scheduled_meet_run(args.config))

    sys.exit("Unsupported command")


if __name__ == "__main__":
    main()
