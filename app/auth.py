"""
One-time Google Calendar authorization.

Run this ONCE:
    python auth.py                                   # local Python
    docker compose run --rm -p 8765:8765 calendar-bot python auth.py   # Docker

It reads credentials.json (OAuth Desktop client downloaded from Google Cloud),
opens a browser for you to approve access, and writes token.json.
The bot then uses token.json (and refreshes it automatically).
"""
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
        print("   Download it from Google Cloud Console → APIs & Services → Credentials")
        print("   (OAuth client ID, application type = Desktop app) and save it here.")
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    if IN_DOCKER:
        print("\n👉 Open the URL below in your browser, approve access, and wait for 'Saved'.\n")
    creds = flow.run_local_server(
        host="localhost",
        bind_addr="0.0.0.0" if IN_DOCKER else None,
        port=AUTH_PORT,
        prompt="consent",
        open_browser=not IN_DOCKER,
    )
    os.makedirs(os.path.dirname(TOKEN_FILE) or ".", exist_ok=True)

    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(creds.to_json())

    print(f"✅ Saved {TOKEN_FILE}. You can now run: python main.py")


if __name__ == "__main__":
    main()
