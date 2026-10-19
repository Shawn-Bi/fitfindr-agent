"""
FitFindr web API (PRD section 7). Wraps the agent in agent.py.

    cd backend
    uvicorn api.main:app --reload --port 8000

Routes
    GET    /health
    GET    /stores                      store status bar (live / paused / coming soon)
    POST   /search                      guest or signed-in search → results, styling, fit card
    GET    /home                        "Picked for your closet" (no live calls)
    GET    /closet/items                POST /closet/items (multipart: data + photo)
    PATCH  /closet/items/{id}           DELETE /closet/items/{id}
    POST   /closet/items/{id}/photo     replace the photo
    GET    /closet/items/{id}/matches   "Finds that go with this"
    GET    /saved   POST /saved   DELETE /saved/{source}/{listing_id}
    GET    /profile PATCH /profile      DELETE /account (hard delete)

Auth: the browser signs in with Supabase and sends `Authorization: Bearer
<access token>`. User data is read and written with that token, so
row-level security applies (DECISIONS.md #13).
"""

import hashlib
import json
import logging
import threading
import time
import uuid
from typing import Literal

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

import config
import supa
from agent import STYLING_UNAVAILABLE, run_agent
from api import catalog
from api.images import PhotoError, process_photo
from api.ratelimit import RateLimiter
from sources import ADAPTERS, quota, recent_pool
from tools import search_with_status

log = logging.getLogger("fitfindr.api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

if config.APP_ENV == "production" and not supa.configured():
    raise SystemExit("Refusing to start: production needs SUPABASE_URL and both Supabase keys.")

app = FastAPI(title="FitFindr API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.FRONTEND_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

search_limiter = RateLimiter(config.SEARCHES_PER_MINUTE)


@app.exception_handler(RequestValidationError)
def _invalid_request(request: Request, exc: RequestValidationError):
    return JSONResponse({"detail": _validation_message(exc)}, status_code=422)


@app.exception_handler(supa.SupabaseError)
def _supabase_error(request: Request, exc: supa.SupabaseError):
    log.error("supabase error on %s: %s", request.url.path, exc)
    status = 401 if exc.status in (401, 403) else 502
    message = ("Please log in again." if status == 401
               else "We couldn't reach your FitFindr data just now. Please try again.")
    return JSONResponse({"detail": message}, status_code=status)


# ── Auth ─────────────────────────────────────────────────────────────────────

class User(BaseModel):
    id: str
    email: str | None = None
    token: str
    metadata: dict = {}


_user_cache: dict[str, tuple[float, User]] = {}
_user_cache_lock = threading.Lock()


def _verify(token: str) -> User:
    key = hashlib.sha256(token.encode()).hexdigest()
    now = time.monotonic()
    with _user_cache_lock:
        hit = _user_cache.get(key)
        if hit and hit[0] > now:
            return hit[1]
    try:
        data = supa.as_user(token).get_user()
    except supa.SupabaseError:
        raise HTTPException(401, "Your session has expired. Please log in again.") from None
    user = User(id=data["id"], email=data.get("email"), token=token,
                metadata=data.get("user_metadata") or {})
    with _user_cache_lock:
        _user_cache[key] = (now + 120, user)
    return user


def optional_user(authorization: str | None = Header(default=None)) -> User | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    if not supa.configured():
        return None
    return _verify(authorization.split(" ", 1)[1].strip())


def require_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise HTTPException(401, "Please log in to do that.")
    return user


def _db(user: User) -> supa.Client:
    return supa.as_user(user.token)


# ── Shared lookups ───────────────────────────────────────────────────────────

def _thumb_path(photo_path: str) -> str:
    return photo_path[:-4] + "_thumb.jpg" if photo_path.endswith(".jpg") else photo_path


def _get_profile(user: User) -> dict:
    rows = _db(user).select("profiles", {"select": "*", "user_id": f"eq.{user.id}"})
    if rows:
        return rows[0]
    created = _db(user).insert("profiles", {"user_id": user.id,
                                            "email_opt_in": bool(user.metadata.get("email_opt_in"))},
                               upsert=True, on_conflict="user_id")
    return created[0]


def _closet(user: User) -> list[dict]:
    return _db(user).select("closet_items", {"select": "*", "user_id": f"eq.{user.id}",
                                             "order": "created_at.desc"})


def _with_photos(user: User, items: list[dict]) -> list[dict]:
    paths = [p for i in items for p in (i["photo_url"], _thumb_path(i["photo_url"]))]
    urls = _db(user).signed_urls(paths) if paths else {}
    out = []
    for item in items:
        out.append({**item, "photo": urls.get(item["photo_url"]),
                    "thumb": urls.get(_thumb_path(item["photo_url"])) or urls.get(item["photo_url"])})
    return out


def _saved_keys(user: User | None) -> set[tuple[str, str]]:
    if user is None:
        return set()
    rows = _db(user).select("saved_items", {"select": "source,listing_id", "user_id": f"eq.{user.id}"})
    return {(r["source"], r["listing_id"]) for r in rows}


def _public_listing(item: dict, saved: set) -> dict:
    return {**item, "saved": (item["platform"], item["id"]) in saved}


def _wardrobe(closet: list[dict]) -> dict:
    return {"items": [{k: c.get(k) for k in ("id", "name", "category", "colors", "style_tags", "notes")}
                      for c in closet]}


# ── Health and store status ──────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"ok": True, "data_mode": config.DATA_MODE, "env": config.APP_ENV}


@app.get("/stores")
def stores():
    statuses = []
    for adapter in ADAPTERS:
        if not adapter.ENABLED:
            statuses += [{"platform": p, "status": "coming_soon"} for p in adapter.PLATFORMS]
        elif config.DATA_MODE == "fixtures":
            statuses += [{"platform": p, "status": "fixtures"} for p in adapter.PLATFORMS]
        else:
            try:
                statuses += [quota.status(adapter.SOURCE, p) for p in adapter.PLATFORMS]
            except quota.QuotaUnknown:
                statuses += [{"platform": p, "status": "error"} for p in adapter.PLATFORMS]
    return {"data_mode": config.DATA_MODE, "stores": catalog.store_panel(statuses, [])}


# ── Search ───────────────────────────────────────────────────────────────────

class SearchIn(BaseModel):
    q: str = Field(min_length=1, max_length=200)
    no_size: bool = False
    no_price: bool = False
    max_price: float | None = Field(default=None, ge=0, le=100000)
    use_profile: bool = True


@app.post("/search")
def search(body: SearchIn, request: Request, user: User | None = Depends(optional_user)):
    key = f"user:{user.id}" if user else f"ip:{request.client.host if request.client else 'unknown'}"
    allowed, retry = search_limiter.allow(key)
    if not allowed:
        raise HTTPException(429, f"That's a lot of searches. Try again in {retry} seconds.",
                            headers={"Retry-After": str(retry)})

    profile = _get_profile(user) if user else None
    closet = _closet(user) if user else []
    parsed, chips = catalog.resolve_filters(
        body.q, profile, no_size=body.no_size, no_price=body.no_price,
        max_price=body.max_price, use_profile=body.use_profile)
    if not parsed["description"]:
        raise HTTPException(422, "Tell us what you're looking for, e.g. “vintage graphic tee”.")

    wardrobe = _wardrobe(closet)
    found: dict = {}

    def direct_search(description, size, max_price):
        results, statuses = search_with_status(description, size, max_price, wardrobe=wardrobe,
                                               limit=config.WEB_RESULT_LIMIT)
        found.update(results=results, statuses=statuses)
        return results

    session = run_agent(body.q, wardrobe, parsed=parsed, search=direct_search)
    results = found.get("results", [])
    panel = catalog.store_panel(found.get("statuses", []), results)
    live_stores = sum(1 for s in panel if s["status"] == "live")
    saved = _saved_keys(user)

    response = {
        "query": body.q,
        "parsed": parsed,
        "chips": chips,
        "results": [_public_listing(r, saved) for r in results],
        "stores": panel,
        "data_mode": config.DATA_MODE,
        "personalized": bool(closet),
        "signed_in": user is not None,
        "closet_count": len(closet),
        "profile": {"sizes": profile.get("sizes") or {}, "budget": profile.get("budget")}
        if profile else None,
        "styling": None,
        "fit_card": None,
        "empty": None,
    }
    if session["error"]:   # nothing matched: no model call was made
        response["empty"] = {"message": catalog.empty_message(parsed, live_stores),
                             "relax": catalog.relax_options(parsed)}
        return response

    if session["styling_error"]:
        response["styling"] = {"text": None, "items": [], "unavailable": STYLING_UNAVAILABLE}
        return response

    outfit = session["outfit_suggestion"] or {}
    by_id = {c["id"]: c for c in closet}
    used = [by_id[i] for i in outfit.get("item_ids") or [] if i in by_id]
    used_items = _with_photos(user, used) if user and used else []
    response["styling"] = {
        "text": outfit.get("text"),
        "items": [{"id": c["id"], "name": c["name"], "category": c["category"], "thumb": c["thumb"]}
                  for c in used_items],
        "unavailable": None,
    }
    response["fit_card"] = session["fit_card"]
    return response


# ── Home ─────────────────────────────────────────────────────────────────────

@app.get("/home")
def home(user: User = Depends(require_user)):
    profile = _get_profile(user)
    closet = _closet(user)
    pool = recent_pool()
    saved = _saved_keys(user)
    if closet:
        picks = catalog.home_picks(pool, closet, profile)
        locked = False
    else:
        picks = catalog.fresh_by_store(pool)
        locked = True
    return {
        "locked": locked,
        "closet_count": len(closet),
        "picks": [{"listing": _public_listing(p["listing"], saved), "reason": p["reason"]}
                  for p in picks],
        "data_mode": config.DATA_MODE,
    }


# ── Closet ───────────────────────────────────────────────────────────────────

SEASONS = ("spring", "summer", "fall", "winter")


def _clean_list(values, max_items: int, max_len: int) -> list[str]:
    out = []
    for v in values or []:
        v = str(v).strip()
        if v and v.lower() not in [o.lower() for o in out]:
            out.append(v[:max_len])
    return out[:max_items]


class ClosetItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    category: Literal["tops", "bottoms", "outerwear", "dresses", "shoes", "accessories"]
    colors: list[str] = Field(min_length=1)
    style_tags: list[str] = []
    size: str | None = Field(default=None, max_length=20)
    brand: str | None = Field(default=None, max_length=40)
    season: list[Literal["spring", "summer", "fall", "winter"]] = []
    notes: str | None = Field(default=None, max_length=300)

    @field_validator("name")
    @classmethod
    def _name(cls, v):
        if not v.strip():
            raise ValueError("Give the item a name.")
        return v.strip()

    @field_validator("colors")
    @classmethod
    def _colors(cls, v):
        v = _clean_list(v, 8, 30)
        if not v:
            raise ValueError("Pick at least one color.")
        return v

    @field_validator("style_tags")
    @classmethod
    def _tags(cls, v):
        return _clean_list(v, 12, 30)

    @field_validator("size", "brand", "notes")
    @classmethod
    def _blank_is_none(cls, v):
        return (v or "").strip() or None


class ClosetItemPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    category: Literal["tops", "bottoms", "outerwear", "dresses", "shoes", "accessories"] | None = None
    colors: list[str] | None = None
    style_tags: list[str] | None = None
    size: str | None = Field(default=None, max_length=20)
    brand: str | None = Field(default=None, max_length=40)
    season: list[Literal["spring", "summer", "fall", "winter"]] | None = None
    notes: str | None = Field(default=None, max_length=300)


async def _read_photo(photo: UploadFile) -> tuple[bytes, bytes]:
    data = await photo.read(config.MAX_PHOTO_BYTES + 1)
    try:
        return process_photo(data)
    except PhotoError as exc:
        raise HTTPException(422, str(exc)) from None


def _upload_photos(user: User, item_id: str, main: bytes, thumb: bytes) -> str:
    path = f"{user.id}/{item_id}.jpg"
    try:
        _db(user).upload(path, main)
        _db(user).upload(_thumb_path(path), thumb)
    except supa.SupabaseError as exc:
        log.error("photo upload failed: %s", exc)
        raise HTTPException(502, "The photo didn't upload. Check your connection and try again.") from None
    return path


@app.get("/closet/items")
def list_closet(user: User = Depends(require_user)):
    items = _with_photos(user, _closet(user))
    counts = {c: 0 for c in catalog.CATEGORIES}
    for item in items:
        counts[item["category"]] = counts.get(item["category"], 0) + 1
    return {"items": items, "counts": counts, "total": len(items)}


@app.post("/closet/items", status_code=201)
async def create_closet_item(data: str = Form(...), photo: UploadFile = File(...),
                             user: User = Depends(require_user)):
    try:
        fields = ClosetItemIn.model_validate(json.loads(data))
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(422, _validation_message(exc)) from None
    main, thumb = await _read_photo(photo)
    item_id = str(uuid.uuid4())
    path = _upload_photos(user, item_id, main, thumb)
    try:
        row = _db(user).insert("closet_items", {"id": item_id, "user_id": user.id, "photo_url": path,
                                                **fields.model_dump()})[0]
    except supa.SupabaseError:
        _db(user).remove([path, _thumb_path(path)])
        raise
    return _with_photos(user, [row])[0]


def _own_item(user: User, item_id: str) -> dict:
    try:
        uuid.UUID(item_id)
    except ValueError:
        raise HTTPException(404, "That item isn't in your closet.") from None
    rows = _db(user).select("closet_items", {"select": "*", "id": f"eq.{item_id}",
                                             "user_id": f"eq.{user.id}"})
    if not rows:
        raise HTTPException(404, "That item isn't in your closet.")
    return rows[0]


@app.get("/closet/items/{item_id}")
def get_closet_item(item_id: str, user: User = Depends(require_user)):
    return _with_photos(user, [_own_item(user, item_id)])[0]


@app.patch("/closet/items/{item_id}")
def update_closet_item(item_id: str, body: ClosetItemPatch, user: User = Depends(require_user)):
    current = _own_item(user, item_id)
    merged = {k: current.get(k) for k in ClosetItemIn.model_fields}
    merged.update(body.model_dump(exclude_unset=True))
    try:
        fields = ClosetItemIn.model_validate(merged)
    except ValueError as exc:
        raise HTTPException(422, _validation_message(exc)) from None
    row = _db(user).update("closet_items", {"id": f"eq.{item_id}", "user_id": f"eq.{user.id}"},
                           fields.model_dump())[0]
    return _with_photos(user, [row])[0]


@app.delete("/closet/items/{item_id}")
def delete_closet_item(item_id: str, user: User = Depends(require_user)):
    item = _own_item(user, item_id)
    _db(user).delete("closet_items", {"id": f"eq.{item_id}", "user_id": f"eq.{user.id}"})
    try:
        _db(user).remove([item["photo_url"], _thumb_path(item["photo_url"])])
    except supa.SupabaseError as exc:   # the row is gone; an orphaned file is only logged
        log.warning("photo cleanup failed for %s: %s", item_id, exc)
    return {"deleted": item_id}


@app.post("/closet/items/{item_id}/photo")
async def replace_photo(item_id: str, photo: UploadFile = File(...),
                        user: User = Depends(require_user)):
    item = _own_item(user, item_id)
    main, thumb = await _read_photo(photo)
    path = _upload_photos(user, item_id, main, thumb)
    if path != item["photo_url"]:
        _db(user).update("closet_items", {"id": f"eq.{item_id}"}, {"photo_url": path})
        item["photo_url"] = path
    else:   # same path: bump updated_at so clients drop cached copies
        _db(user).update("closet_items", {"id": f"eq.{item_id}"}, {"name": item["name"]})
    return _with_photos(user, [item])[0]


@app.get("/closet/items/{item_id}/matches")
def closet_item_matches(item_id: str, user: User = Depends(require_user)):
    item = _own_item(user, item_id)
    profile = _get_profile(user)
    budget = float(profile["budget"]) if profile.get("budget") else None
    saved = _saved_keys(user)
    picks = catalog.item_matches(recent_pool(), item, budget)
    return {"matches": [{"listing": _public_listing(p["listing"], saved), "reason": p["reason"]}
                        for p in picks],
            "data_mode": config.DATA_MODE}


# ── Saved ────────────────────────────────────────────────────────────────────

class ListingIn(BaseModel):
    id: str = Field(min_length=1, max_length=300)
    title: str = Field(min_length=1, max_length=500)
    price: float = Field(ge=0)
    size: str | None = None
    platform: Literal["depop", "poshmark", "mercari", "etsy", "ebay", "fb_marketplace"]
    url: str = Field(min_length=8, max_length=2000)
    image_url: str | None = None
    condition: str | None = None
    updated_at: str | None = None
    category: str | None = None

    @field_validator("url", "image_url")
    @classmethod
    def _https(cls, v):
        if v is not None and not v.startswith("https://"):
            raise ValueError("Listing links must be https.")
        return v


class SaveIn(BaseModel):
    listing: ListingIn


@app.get("/saved")
def list_saved(user: User = Depends(require_user)):
    rows = _db(user).select("saved_items", {"select": "*", "user_id": f"eq.{user.id}",
                                            "order": "saved_at.desc"})
    return {"items": rows}


@app.post("/saved", status_code=201)
def save_listing(body: SaveIn, user: User = Depends(require_user)):
    listing = body.listing.model_dump()
    row = _db(user).insert("saved_items", {
        "user_id": user.id, "listing_id": listing["id"], "source": listing["platform"],
        "listing": listing, "available": True}, upsert=True, on_conflict="user_id,source,listing_id")
    return row[0]


@app.delete("/saved/{source}/{listing_id:path}")
def unsave_listing(source: str, listing_id: str, user: User = Depends(require_user)):
    _db(user).delete("saved_items", {"user_id": f"eq.{user.id}", "source": f"eq.{source}",
                                     "listing_id": f"eq.{listing_id}"})
    return {"deleted": listing_id}


# ── Profile and account ──────────────────────────────────────────────────────

class Sizes(BaseModel):
    top: str | None = Field(default=None, max_length=10)
    waist: str | None = Field(default=None, max_length=10)
    length: str | None = Field(default=None, max_length=10)
    shoe: str | None = Field(default=None, max_length=10)


class ProfilePatch(BaseModel):
    sizes: Sizes | None = None
    styles: list[str] | None = None
    colors: list[str] | None = None
    budget: float | None = Field(default=None, ge=0, le=100000)
    email_opt_in: bool | None = None


def _profile_out(row: dict) -> dict:
    created, updated = row.get("created_at") or "", row.get("updated_at") or ""
    return {**row, "onboarded": bool(updated and created and updated[:19] != created[:19])}


@app.get("/profile")
def get_profile(user: User = Depends(require_user)):
    return {**_profile_out(_get_profile(user)), "email": user.email}


@app.patch("/profile")
def update_profile(body: ProfilePatch, user: User = Depends(require_user)):
    current = _get_profile(user)
    patch = body.model_dump(exclude_unset=True)
    if "sizes" in patch:
        patch["sizes"] = {k: (v or "").strip() for k, v in (patch["sizes"] or {}).items() if (v or "").strip()}
    for key in ("styles", "colors"):
        if key in patch:
            patch[key] = _clean_list(patch[key], 12, 30)
    if not patch:   # "Skip for now": touch the row so onboarding counts as done
        patch = {"email_opt_in": current.get("email_opt_in", False)}
    row = _db(user).update("profiles", {"user_id": f"eq.{user.id}"}, patch)[0]
    return {**_profile_out(row), "email": user.email}


@app.delete("/account")
def delete_account(user: User = Depends(require_user)):
    """Immediate hard delete: photos, rows, then the auth user (DECISIONS.md #12)."""
    db = _db(user)
    try:
        db.remove(db.list_folder(user.id))
    except supa.SupabaseError as exc:
        log.error("photo removal failed during account deletion: %s", exc)
        raise HTTPException(502, "We couldn't delete your photos. Nothing was deleted; please try again.") from None
    for table in ("closet_items", "saved_items", "profiles"):
        db.delete(table, {"user_id": f"eq.{user.id}"})
    supa.service().admin_delete_user(user.id)
    with _user_cache_lock:
        _user_cache.clear()
    return {"deleted": True}


def _validation_message(exc: Exception) -> str:
    errors = getattr(exc, "errors", None)
    if callable(errors):
        first = errors()[0]
        field = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        message = str(first.get("msg", "")).removeprefix("Value error, ")
        return f"{field}: {message}" if field else message
    return "The item details couldn't be read. Please check the form and try again."
