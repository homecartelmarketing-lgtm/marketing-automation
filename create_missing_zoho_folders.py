"""CLI: create the per-style subfolders under each Zoho WorkDrive category.

Creating a folder that already exists is reported as a warning and skipped, so
the script is safe to re-run.
"""

from __future__ import annotations

import os
import sys

import requests
from dotenv import load_dotenv

from content_automation.errors import ConfigurationError
from content_automation.http import request_with_retry, response_error


load_dotenv()

ZOHO_TOKEN_URL = "https://accounts.zoho.com/oauth/v2/token"
ZOHO_FILES_URL = "https://workdrive.zoho.com/api/v1/files"

CREDENTIAL_VARS = ("ZOHO_CLIENT_ID", "ZOHO_CLIENT_SECRET", "ZOHO_REFRESH_TOKEN")

# Style subfolders that should exist under every category below.
STYLE_FOLDERS = ("Midcentury", "Bohemian", "Bauhaus", "Resort")

# Zoho WorkDrive folder id per product category.
PARENT_FOLDERS = {
    "Chandelier": "1jvesa9d41b8a1b104bebb415529d57e05d45",
    "Table lamps": "h9prx224a7ad812fa48939e3033c482810c5a",
    "Rechargeable Table Lamps": "h9prxfb49d8ee279b4a03b879d90a48150b53",
    "Floor Lamps": "fgthe556ddf3375b0447d8eadb15ac058a049",
    "Pendant Lights": "fgtheace4be50836a4027917ba13667d771d5",
    "Cluster Chandelier": "h9prx0690a1f30ad14ad2b0cb2c5f68dd6972",
    "Ceiling Lights": "h9prx5db1574946b34468bfcc329c599b0c83",
    "Wall lights": "h9prx235361b3752a4ae3af700a4b0fc6ce7e",
}


def load_credentials() -> dict[str, str]:
    values = {name: (os.environ.get(name) or "").strip() for name in CREDENTIAL_VARS}
    if missing := [name for name, value in values.items() if not value]:
        raise ConfigurationError(
            "Missing Zoho WorkDrive credentials in .env: " + ", ".join(missing)
        )
    return values


def fetch_access_token(session: requests.Session, credentials: dict[str, str]) -> str:
    print("[INFO] Fetching Zoho access token...")
    response = request_with_retry(
        session,
        "POST",
        ZOHO_TOKEN_URL,
        retry_non_idempotent=True,
        data={
            "client_id": credentials["ZOHO_CLIENT_ID"],
            "client_secret": credentials["ZOHO_CLIENT_SECRET"],
            "refresh_token": credentials["ZOHO_REFRESH_TOKEN"],
            "grant_type": "refresh_token",
        },
    )
    if not response.ok:
        raise response_error(response, "Zoho token refresh")
    token = str(response.json().get("access_token") or "")
    if not token:
        raise response_error(response, "Zoho token refresh returned no access token")
    return token


def create_folder(
    session: requests.Session,
    access_token: str,
    folder_name: str,
    parent_id: str,
) -> bool:
    """Create one folder. False when Zoho rejects it (commonly: already there)."""
    response = request_with_retry(
        session,
        "POST",
        ZOHO_FILES_URL,
        # A duplicate folder is rejected outright, so replaying a 429 is safe.
        retry_non_idempotent=True,
        retry_server_errors=False,
        headers={
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Accept": "application/vnd.api+json",
            "Content-Type": "application/json",
        },
        json={
            "data": {
                "attributes": {"name": folder_name, "parent_id": parent_id},
                "type": "files",
            }
        },
    )
    if response.ok:
        print(f"[OK] Created folder '{folder_name}' in parent '{parent_id}'")
        return True
    print(
        f"[WARN] Failed to create folder '{folder_name}' in parent "
        f"'{parent_id}': {response.text[:300]}"
    )
    return False


def main() -> int:
    credentials = load_credentials()
    session = requests.Session()
    access_token = fetch_access_token(session, credentials)

    created = 0
    for category, parent_id in PARENT_FOLDERS.items():
        print(f"\n--- Processing category: {category} ---")
        for style in STYLE_FOLDERS:
            if create_folder(session, access_token, style, parent_id):
                created += 1

    total = len(PARENT_FOLDERS) * len(STYLE_FOLDERS)
    print(f"\n[SUMMARY] Created {created}/{total} folders (existing ones are skipped).")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ConfigurationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        raise SystemExit(2)
