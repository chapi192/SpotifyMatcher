from fastapi import APIRouter, Request, Body
import time

from web.spotify_auth import get_spotify_client, build_oauth
from web.state import PLAYLIST_CACHE, PLAYLIST_DATA_CACHE, BUILD_STATE, USER_BUILD_STATE
from web.routes.build import start_incremental_build

router = APIRouter()

@router.get("/api/playlists")
def api_playlists(request: Request):

    sp = get_spotify_client(request)
    if not sp:
        return {"error": "Not logged in"}

    user_id = sp.current_user()["id"]

    cache = PLAYLIST_CACHE.get(user_id)
    if cache and time.time() - cache["fetched_at"] < 300:
        return {"cache_hit": True, "playlists": cache["data"]}

    playlists = []
    results = sp.current_user_playlists(limit=50)

    while True:
        for p in results["items"]:
            playlists.append({
                "id": p["id"],
                "name": p["name"],
                "track_count": p["tracks"]["total"],
                "image": p["images"][0]["url"] if p.get("images") else None
            })

        if results["next"]:
            results = sp.next(results)
        else:
            break

    # add liked songs
    try:
        liked_meta = sp.current_user_saved_tracks(limit=1)
        playlists.append({
            "id": "__liked__",
            "name": "Liked Songs",
            "track_count": liked_meta["total"],
            "image": None
        })
    except Exception:
        pass

    PLAYLIST_CACHE[user_id] = {
        "data": playlists,
        "fetched_at": time.time()
    }

    return {"cache_hit": False, "playlists": playlists}

# =====================================================================================
# SELECTION API
# =====================================================================================

@router.post("/api/selection")
def update_selection(request: Request, data: dict = Body(...)):

    selected_ids = list(dict.fromkeys(data.get("selected_ids", [])))
    breakdown_source = data.get("breakdown_source")
    hidden_ids = data.get("hidden_ids", [])

    if breakdown_source and breakdown_source not in selected_ids:
        breakdown_source = None

    request.session["selected_playlists"] = selected_ids
    request.session["breakdown_source"] = breakdown_source
    request.session["hidden_playlists"] = hidden_ids

    sp = get_spotify_client(request)
    if sp:
        user_id = sp.current_user()["id"]
        user_cache = PLAYLIST_DATA_CACHE.get(user_id, {})

        missing = [pid for pid in selected_ids if pid not in user_cache]

        if missing:

            # Compute total tracks for missing playlists
            total_tracks = 0
            for pid in missing:
                if pid == "__liked__":
                    meta = sp.current_user_saved_tracks(limit=1)
                    total_tracks += meta["total"]
                else:
                    pl = sp.playlist(pid, fields="tracks.total")
                    total_tracks += pl["tracks"]["total"]

            BUILD_STATE.setdefault(user_id, {"version": 0})
            BUILD_STATE[user_id]["version"] += 1
            version = BUILD_STATE[user_id]["version"]

            # Initialize progress state
            USER_BUILD_STATE[user_id] = {
                "version": version,
                "status": "building",
                "total_tracks": total_tracks,
                "tracks_processed": 0
            }

            start_incremental_build(
                request,
                user_id=user_id,
                version=version,
                playlist_ids=missing
            )

    return {
        "status": "ok",
        "selected_ids": selected_ids,
        "breakdown_source": breakdown_source,
        "hidden_ids": hidden_ids
    }


@router.get("/api/selection")
def get_selection(request: Request):
    return {
        "selected_ids": request.session.get("selected_playlists", []),
        "breakdown_source": request.session.get("breakdown_source"),
        "hidden_ids": request.session.get("hidden_playlists", [])
    }