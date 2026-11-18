"""
Create the one test account automated tests use (DECISIONS.md #9).

    cd backend
    python scripts/create_test_user.py

Uses the service-role key to create a pre-confirmed user (email verification
would otherwise block a brand-new sign-up), then appends TEST_USER_EMAIL and
TEST_USER_PASSWORD to the repo's .env. The password is generated here and is
never printed. Does nothing if .env already has TEST_USER_EMAIL.
"""

import os
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

import config  # noqa: E402

ENV_FILE = config.REPO_ROOT / ".env"
EMAIL = "fitfindr.test.user@example.com"


def main() -> None:
    if os.getenv("TEST_USER_EMAIL"):
        print("TEST_USER_EMAIL is already set in .env; nothing to do.")
        return
    password = secrets.token_urlsafe(18)          # 24 characters
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    r = httpx.post(f"{config.SUPABASE_URL}/auth/v1/admin/users",
                   headers={"apikey": key, "Authorization": f"Bearer {key}"},
                   json={"email": EMAIL, "password": password, "email_confirm": True,
                         "user_metadata": {"test_account": True}},
                   timeout=20)
    if r.status_code >= 400:
        sys.exit(config.redact(f"Could not create the test user: HTTP {r.status_code} {r.text[:200]}"))
    text = ENV_FILE.read_text(encoding="utf-8")
    newline = "" if text.endswith("\n") else "\n"
    with ENV_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{newline}# Test account for automated tests (created by scripts/create_test_user.py)\n"
                f"TEST_USER_EMAIL={EMAIL}\nTEST_USER_PASSWORD={password}\n")
    print(f"Created test user {EMAIL} (id {r.json().get('id')}); login saved to .env.")


if __name__ == "__main__":
    main()
