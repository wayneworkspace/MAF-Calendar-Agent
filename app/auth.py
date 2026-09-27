"""One-time Google OAuth 2.0 authentication utility for Calendar Agent.

Run locally or inside Docker container to generate data/token.json credential file.
"""
from __future__ import annotations

import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
TOKEN_FILE = os.getenv("GOOGLE_TOKEN_FILE", "token.json")
AUTH_PORT = int(os.getenv("AUTH_PORT", "8765"))
IN_DOCKER = os.path.exists("/.dockerenv")


def main() -> None:
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"❌ {CREDENTIALS_FILE} not found.")
        print("   Download OAuth Desktop Client credentials from Google Cloud Console")
        print("   and place them at the designated credentials file path.")
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    if IN_DOCKER:
        print("\n👉 Open the generated URL in your web browser to approve access:\n")

    creds = flow.run_local_server(
        host="localhost",
        bind_addr="0.0.0.0" if IN_DOCKER else None,
        port=AUTH_PORT,
        prompt="consent",
        open_browser=not IN_DOCKER,
    )

    parent_dir = os.path.dirname(TOKEN_FILE)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(creds.to_json())

    print(f"✅ Authorization successful. Saved token to {TOKEN_FILE}.")


if __name__ == "__main__":
    main()
