"""
A thin Supabase client over plain HTTP (PostgREST, Storage, Auth).

Two ways in, on purpose (DECISIONS.md #13):

    supa.as_user(token)   user rows and photos, with the user's own access token,
                          so row-level security applies.
    supa.service()        server-only tables (api_usage, search_cache) and the
                          account-deletion admin call. Uses the service-role key.

Keys are read from the environment and never logged. Error messages pass
through config.redact() before they go anywhere.
"""

import os
import urllib.parse

import httpx

import config

TIMEOUT = httpx.Timeout(15.0, connect=10.0)
PHOTO_BUCKET = "closet-photos"


class SupabaseError(RuntimeError):
    def __init__(self, status: int, message: str):
        self.status = status
        super().__init__(config.redact(message))


def configured() -> bool:
    return bool(config.SUPABASE_URL and os.getenv("SUPABASE_ANON_KEY")
                and os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


def _check(response: httpx.Response) -> httpx.Response:
    if response.status_code >= 400:
        raise SupabaseError(response.status_code,
                            f"Supabase {response.request.method} {response.request.url.path} "
                            f"returned HTTP {response.status_code}: {response.text[:300]}")
    return response


class Client:
    """One set of credentials. Every method raises SupabaseError on HTTP errors."""

    def __init__(self, bearer: str):
        anon = os.getenv("SUPABASE_ANON_KEY", "").strip()
        service = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        # The apikey header picks the project role; the bearer picks the user.
        apikey = service if bearer == service else anon
        self.base = config.SUPABASE_URL
        self.headers = {"apikey": apikey, "Authorization": f"Bearer {bearer}"}

    # ── PostgREST ────────────────────────────────────────────────────────────
    def select(self, table: str, params: dict | None = None) -> list[dict]:
        r = httpx.get(f"{self.base}/rest/v1/{table}", params=params or {},
                      headers=self.headers, timeout=TIMEOUT)
        return _check(r).json()

    def insert(self, table: str, row: dict | list, upsert: bool = False,
               on_conflict: str | None = None) -> list[dict]:
        prefer = "return=representation"
        if upsert:
            prefer += ",resolution=merge-duplicates"
        params = {"on_conflict": on_conflict} if on_conflict else None
        r = httpx.post(f"{self.base}/rest/v1/{table}", params=params, json=row,
                       headers={**self.headers, "Prefer": prefer}, timeout=TIMEOUT)
        return _check(r).json()

    def update(self, table: str, filters: dict, patch: dict) -> list[dict]:
        r = httpx.patch(f"{self.base}/rest/v1/{table}", params=filters, json=patch,
                        headers={**self.headers, "Prefer": "return=representation"},
                        timeout=TIMEOUT)
        return _check(r).json()

    def delete(self, table: str, filters: dict) -> list[dict]:
        r = httpx.delete(f"{self.base}/rest/v1/{table}", params=filters,
                         headers={**self.headers, "Prefer": "return=representation"},
                         timeout=TIMEOUT)
        return _check(r).json()

    def rpc(self, function: str, args: dict):
        r = httpx.post(f"{self.base}/rest/v1/rpc/{function}", json=args,
                       headers=self.headers, timeout=TIMEOUT)
        return _check(r).json()

    # ── Storage (private closet-photos bucket) ───────────────────────────────
    def upload(self, path: str, data: bytes, content_type: str = "image/jpeg") -> None:
        r = httpx.post(f"{self.base}/storage/v1/object/{PHOTO_BUCKET}/{_quote(path)}",
                       content=data,
                       headers={**self.headers, "Content-Type": content_type,
                                "x-upsert": "true", "cache-control": "3600"},
                       timeout=httpx.Timeout(60.0, connect=10.0))
        _check(r)

    def remove(self, paths: list[str]) -> None:
        if not paths:
            return
        r = httpx.request("DELETE", f"{self.base}/storage/v1/object/{PHOTO_BUCKET}",
                          json={"prefixes": paths}, headers=self.headers, timeout=TIMEOUT)
        _check(r)

    def list_folder(self, folder: str) -> list[str]:
        r = httpx.post(f"{self.base}/storage/v1/object/list/{PHOTO_BUCKET}",
                       json={"prefix": folder, "limit": 1000},
                       headers=self.headers, timeout=TIMEOUT)
        return [f"{folder}/{o['name']}" for o in _check(r).json() if o.get("name")]

    def signed_urls(self, paths: list[str], expires_in: int = 3600) -> dict[str, str]:
        """path → short-lived signed URL. Missing files are left out."""
        paths = [p for p in dict.fromkeys(paths) if p]
        if not paths:
            return {}
        r = httpx.post(f"{self.base}/storage/v1/object/sign/{PHOTO_BUCKET}",
                       json={"expiresIn": expires_in, "paths": paths},
                       headers=self.headers, timeout=TIMEOUT)
        out = {}
        for entry in _check(r).json():
            signed = entry.get("signedURL") or entry.get("signedUrl")
            if signed and not entry.get("error"):
                out[entry["path"]] = f"{self.base}/storage/v1{signed}"
        return out

    # ── Auth ─────────────────────────────────────────────────────────────────
    def get_user(self) -> dict:
        r = httpx.get(f"{self.base}/auth/v1/user", headers=self.headers, timeout=TIMEOUT)
        return _check(r).json()

    def admin_delete_user(self, user_id: str) -> None:
        r = httpx.delete(f"{self.base}/auth/v1/admin/users/{user_id}",
                         headers=self.headers, timeout=TIMEOUT)
        _check(r)


def _quote(path: str) -> str:
    return urllib.parse.quote(path, safe="/")


def as_user(token: str) -> Client:
    return Client(token)


def service() -> Client:
    return Client(os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip())
