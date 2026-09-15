import time

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from web.catalog import load_playlist_dataset, load_selection, save_selection
from web.services.profile_library import build_playlist_profiles
from web.spotify_auth import get_spotify_client, get_user_id
from web.state import PLAYLIST_CACHE, PLAYLIST_DATA_CACHE


router = APIRouter()


def _playlist_track_total(playlist):
    container = playlist.get("items") or playlist.get("tracks") or {}
    return container.get("total", 0)


@router.get("/api/playlists")
def api_playlists(request: Request):
    sp = get_spotify_client(request)
    if not sp:
        return JSONResponse({"error": "Not logged in"}, status_code=401)

    user_id = get_user_id(request)
    cache = PLAYLIST_CACHE.get(user_id)
    if cache and time.time() - cache["fetched_at"] < 300:
        return {"cache_hit": True, "playlists": cache["data"]}

    playlists = []
    results = sp.current_user_playlists(limit=50)
    while True:
        for playlist in results.get("items") or []:
            owner_id = (playlist.get("owner") or {}).get("id")
            collaborative = bool(playlist.get("collaborative"))
            if owner_id != user_id and not collaborative:
                continue
            playlists.append({
                "id": playlist["id"],
                "name": playlist.get("name") or "Untitled playlist",
                "track_count": _playlist_track_total(playlist),
                "image": (playlist.get("images") or [{}])[0].get("url"),
                "is_owner": owner_id == user_id,
                "collaborative": collaborative,
                "snapshot_id": playlist.get("snapshot_id"),
            })
        if not results.get("next"):
            break
        results = sp.next(results)

    liked_meta = sp.current_user_saved_tracks(limit=1)
    playlists.append({
        "id": "__liked__",
        "name": "Liked Songs",
        "track_count": liked_meta.get("total", 0),
        "image": None,
        "is_owner": True,
        "collaborative": False,
        "snapshot_id": None,
    })

    PLAYLIST_CACHE[user_id] = {"data": playlists, "fetched_at": time.time()}
    return {"cache_hit": False, "playlists": playlists}


@router.post("/api/selection")
def update_selection(request: Request, data: dict = Body(...)):
    sp = get_spotify_client(request)
    if not sp:
        return JSONResponse({"error": "Not logged in"}, status_code=401)
    user_id = get_user_id(request)

    selected_ids = list(dict.fromkeys(
        value for value in data.get("selected_ids", []) if isinstance(value, str)
    ))
    hidden_ids = list(dict.fromkeys(
        value for value in data.get("hidden_ids", []) if isinstance(value, str)
    ))
    breakdown_source = data.get("breakdown_source")
    if breakdown_source not in selected_ids:
        breakdown_source = None

    save_selection(user_id, selected_ids, hidden_ids, breakdown_source)

    missing = []
    for playlist_id in selected_ids:
        if playlist_id in PLAYLIST_DATA_CACHE.get(user_id, {}):
            continue
        persisted = load_playlist_dataset(user_id, playlist_id)
        if not persisted:
            missing.append(playlist_id)
            continue
        profile = build_playlist_profiles({playlist_id: persisted}).get(playlist_id)
        PLAYLIST_DATA_CACHE.setdefault(user_id, {})[playlist_id] = {
            "dataset": persisted,
            "profile": profile,
            "fetched_at": 0,
        }

    return {
        "status": "ok" if not missing else "sync_required",
        "selected_ids": selected_ids,
        "breakdown_source": breakdown_source,
        "hidden_ids": hidden_ids,
        "missing": missing,
    }


@router.get("/api/selection")
def get_selection(request: Request):
    if not request.session.get("token_info"):
        return JSONResponse({"error": "Not logged in"}, status_code=401)
    user_id = get_user_id(request)
    return load_selection(user_id)
