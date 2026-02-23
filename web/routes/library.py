from fastapi import APIRouter, Request

from web.spotify_auth import get_spotify_client, build_oauth
from web.state import PLAYLIST_DATA_CACHE

router = APIRouter()

def get_active_dataset_and_profiles(request: Request, sp):
    user_id = sp.current_user()["id"]
    selected_ids = request.session.get("selected_playlists", [])

    if not selected_ids:
        return None, None, {"status": "empty"}

    user_cache = PLAYLIST_DATA_CACHE.get(user_id, {})
    missing = [pid for pid in selected_ids if pid not in user_cache]

    if missing:
        return None, None, {"status": "missing", "missing": missing}

    dataset = {pid: user_cache[pid]["dataset"] for pid in selected_ids}
    profiles = {
        pid: user_cache[pid]["profile"]
        for pid in selected_ids
        if user_cache[pid].get("profile")
    }

    return dataset, profiles, None


@router.get("/api/library")
def get_library(request: Request):

    sp = get_spotify_client(request)
    if not sp:
        return {"error": "Not logged in"}

    dataset, _profiles, err = get_active_dataset_and_profiles(request, sp)

    if err:
        if err["status"] == "empty":
            return {"status": "empty"}

        user_id = sp.current_user()["id"]
        build_state = USER_BUILD_STATE.get(user_id, {})

        if build_state.get("status") == "building":
            return {
                "status": "building",
                "missing": err.get("missing", [])
            }

        # Build not running, cache missing
        return {
            "status": "not_built",
            "missing": err.get("missing", [])
        }

    playlists_output = []
    total_tracks = 0

    for pid, playlist in dataset.items():
        track_count = len(playlist["tracks"])
        total_tracks += track_count

        playlists_output.append({
            "playlist_id": playlist["playlist_id"],
            "playlist_name": playlist["playlist_name"],
            "track_count": track_count,
            "image": playlist.get("image")  # <-- add this
        })

    return {
        "status": "ready",
        "playlist_count": len(playlists_output),
        "total_tracks": total_tracks,
        "playlists": playlists_output
    }
