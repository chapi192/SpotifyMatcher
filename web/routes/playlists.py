from fastapi import APIRouter, Request, Body
import time
from web.utils.debug import build_debug
from web.spotify_auth import get_spotify_client, build_oauth
from web.state import PLAYLIST_CACHE, PLAYLIST_DATA_CACHE, BUILD_STATE, USER_BUILD_STATE
from web.routes.build import start_incremental_build

router = APIRouter()

@router.get("/api/playlists")
def api_playlists(request: Request):

    sp = get_spotify_client(request)
    if not sp:
        return {"error": "Not logged in"}

    from web.spotify_auth import get_user_id
    user_id = get_user_id(request)

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
                "image": p["images"][0]["url"] if p.get("images") else None,
                "is_owner": p["owner"]["id"] == user_id
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
            "image": None,
            "is_owner": True
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

    from web.spotify_auth import get_user_id
    user_id = get_user_id(request)

    build_debug(f"User updated selection → {selected_ids}")

    existing_state = USER_BUILD_STATE.get(user_id)

    if existing_state:

        tracked = set(existing_state.get("playlist_track_map", {}).keys())
        removed = tracked - set(selected_ids)

        if removed:
            build_debug(f"Playlists removed from build → {removed}")

        for pid in removed:

            removed_tracks = existing_state["playlist_track_map"].get(pid, 0)

            existing_state["total_tracks"] -= removed_tracks

            if pid in PLAYLIST_DATA_CACHE.get(user_id, {}):
                existing_state["tracks_processed"] -= removed_tracks

            existing_state["tracks_processed"] = max(existing_state["tracks_processed"], 0)
            existing_state["total_tracks"] = max(existing_state["total_tracks"], 0)

            existing_state["playlist_track_map"].pop(pid, None)

        if existing_state and not existing_state["playlist_track_map"]:
            build_debug("All playlists removed — cancelling build")

            # bump version so worker/progress callbacks stop immediately
            existing_state["version"] = existing_state.get("version", 0) + 1

            existing_state["status"] = "cancelled"
            existing_state["tracks_processed"] = 0
            existing_state["total_tracks"] = 0

    if breakdown_source and breakdown_source not in selected_ids:
        breakdown_source = None

    request.session["selected_playlists"] = selected_ids
    request.session["breakdown_source"] = breakdown_source
    request.session["hidden_playlists"] = hidden_ids

    sp = get_spotify_client(request)
    if sp:

        user_cache = PLAYLIST_DATA_CACHE.get(user_id, {})

        existing_state = USER_BUILD_STATE.get(user_id)

        tracked = set()
        if existing_state:
            tracked = set(existing_state.get("playlist_track_map", {}).keys())

        missing = [
            pid for pid in selected_ids
            if pid not in user_cache and pid not in tracked
        ]

        build_debug(f"Playlists missing from cache → {missing}")

        if missing:

            playlist_cache = PLAYLIST_CACHE.get(user_id, {})
            cached_playlists = playlist_cache.get("data", [])

            track_lookup = {p["id"]: p["track_count"] for p in cached_playlists}
            name_lookup = {p["id"]: p["name"] for p in cached_playlists}

            BUILD_STATE.setdefault(user_id, {"version": 0})
            BUILD_STATE[user_id]["version"] += 1
            version = BUILD_STATE[user_id]["version"]

            existing_state = USER_BUILD_STATE.get(user_id)

            if existing_state and existing_state["status"] == "building":

                build_debug("Extending current build")

                for pid in missing:

                    if pid in existing_state["playlist_track_map"]:
                        continue

                    tracks = track_lookup.get(pid)

                    if tracks is None or tracks == 0:

                            if pid == "__liked__":
                                meta = sp.current_user_saved_tracks(limit=1)
                                tracks = meta["total"]
                            else:
                                pl = sp.playlist(pid, fields="name,tracks.total")
                                tracks = pl["tracks"]["total"]

                            track_lookup[pid] = tracks

                    existing_state["playlist_track_map"][pid] = tracks
                    existing_state["total_tracks"] += tracks

                    build_debug(f"Added playlist to build → {name_lookup.get(pid,pid)} ({tracks} tracks)")

            else:

                total_tracks = 0

                for pid in missing:

                    tracks = track_lookup.get(pid)

                    if tracks is None or tracks == 0:

                        if pid == "__liked__":
                            meta = sp.current_user_saved_tracks(limit=1)
                            tracks = meta["total"]
                        else:
                            pl = sp.playlist(pid, fields="name,tracks.total")
                            tracks = pl["tracks"]["total"]

                        track_lookup[pid] = tracks

                    total_tracks += tracks

                    build_debug(f"Track count resolved → {name_lookup.get(pid,pid)} : {tracks}")

                USER_BUILD_STATE[user_id] = {
                    "version": version,
                    "status": "building",
                    "total_tracks": total_tracks,
                    "tracks_processed": 0,
                    "playlist_track_map": {
                        pid: track_lookup.get(pid, 0) for pid in missing
                    }
                }

                existing_state = USER_BUILD_STATE[user_id]

                build_debug(f"Starting new build v{version} → {missing}")

            if not existing_state or existing_state["version"] == version:

                start_incremental_build(
                    request,
                    user_id=user_id,
                    version=version,
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