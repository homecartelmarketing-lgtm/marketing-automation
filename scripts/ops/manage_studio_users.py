#!/usr/bin/env python
"""Manage Studio login accounts (email + password).

    python scripts/ops/manage_studio_users.py add you@homecartel.net [--role admin|user]
    python scripts/ops/manage_studio_users.py list
    python scripts/ops/manage_studio_users.py set-password you@homecartel.net
    python scripts/ops/manage_studio_users.py remove you@homecartel.net
    python scripts/ops/manage_studio_users.py env you@homecartel.net [--second]   # values to paste into Railway

Accounts are stored in STUDIO_USERS_PATH (default output/studio_users.json).
Passwords are read with a hidden prompt, never from the command line.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UI_CONTROL = ROOT / "UI Control"
for path in (ROOT, UI_CONTROL):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from routes import studio_auth  # noqa: E402


def _prompt_password() -> str:
    first = getpass.getpass("Password: ")
    if first != getpass.getpass("Confirm password: "):
        raise ValueError("Passwords do not match.")
    return first


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="Create an account")
    add.add_argument("email")
    add.add_argument("--role", choices=studio_auth.VALID_ROLES, default="user")

    sub.add_parser("list", help="List accounts")

    reset = sub.add_parser("set-password", help="Change an account's password")
    reset.add_argument("email")

    env = sub.add_parser("env", help="Print the Railway variables that recreate an existing account")
    env.add_argument("email")
    env.add_argument("--second", action="store_true", help="Print the STUDIO_ADMIN2_* names for the second account")

    remove = sub.add_parser("remove", help="Delete an account (ends its sessions)")
    remove.add_argument("email")
    remove.add_argument(
        "--force",
        action="store_true",
        help="Allow removing the last account (with no DASHBOARD_PIN this OPENS the Studio to everyone)",
    )

    args = parser.parse_args(argv)

    try:
        if args.command == "add":
            user = studio_auth.add_user(args.email, _prompt_password(), args.role)
            print(f"Created {user['email']} ({user['role']}).")
        elif args.command == "list":
            users = studio_auth.load_users()
            if not users:
                print("No accounts yet.")
            for email, record in sorted(users.items()):
                origin = "env" if record.get("seeded") else record.get("created_at", "")
                print(f"{email}\t{record.get('role', 'user')}\t{origin}")
        elif args.command == "set-password":
            studio_auth.set_password(args.email, _prompt_password())
            print(f"Password updated for {studio_auth.normalize_email(args.email)}.")
        elif args.command == "env":
            email = studio_auth.normalize_email(args.email)
            record = studio_auth.load_users().get(email)
            if record is None:
                raise ValueError(f"No such user: {email}")
            slot = "STUDIO_ADMIN2" if args.second else "STUDIO_ADMIN"
            print("Add these two variables in Railway (Variables tab). Never commit them or put them in a chat.")
            print(f"{slot}_EMAIL={record['email']}")
            print(f"{slot}_PASSWORD_HASH={record['password_hash']}")
        elif args.command == "remove":
            if len(studio_auth.load_users()) <= 1 and not args.force:
                raise ValueError(
                    "That is the last account; removing it turns login off and opens the Studio. "
                    "Add another account first, or pass --force."
                )
            studio_auth.remove_user(args.email)
            print(f"Removed {studio_auth.normalize_email(args.email)}.")
    except ValueError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
