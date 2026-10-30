"""
Bring the test account up to the v2 profile (B3), through the real API:
"Shopping for: Women", sizes as lists, a $10–$40 budget range, and every
closet item marked as women's (B2). Idempotent.

    cd backend
    python scripts/setup_v2_test_account.py

Only ever touches the test account from .env (TEST_USER_EMAIL / TEST_USER_PASSWORD).
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("FITFINDR_DATA_MODE", "fixtures")

from unittest import mock  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

import api.main as api_main  # noqa: E402
from api.main import app  # noqa: E402
from scripts.seed_test_closet import sign_in  # noqa: E402


def main() -> None:
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {sign_in()}"}
    current = client.get("/profile", headers=headers).json()
    sizes = current["sizes"]   # legacy keys already read into v2 lists by the API
    r = client.patch("/profile", headers=headers, json={
        "gender": "women",
        "sizes": sizes,
        "budget_min": 10,
        "budget": current.get("budget") or 40,
    })
    print(f"{r.status_code} profile → gender {r.json().get('gender')}, sizes {r.json().get('sizes')}, "
          f"budget {r.json().get('budget_min')}–{r.json().get('budget')}")

    # A PATCH would rebuild each outfit in the background; this script only tags
    # (scripts/generate_outfits.py builds them, sharing live searches).
    with mock.patch.object(api_main, "STYLING_FIELDS", ()):
        for item in client.get("/closet/items", headers=headers).json()["items"]:
            if item.get("gender") != "women":
                r = client.patch(f"/closet/items/{item['id']}", headers=headers, json={"gender": "women"})
                print(f"{r.status_code} {item['name']} → women")


if __name__ == "__main__":
    main()
