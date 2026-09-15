from fastapi import APIRouter, Request

from web.spotify_auth import get_spotify_client, build_oauth
from web.state import PLAYLIST_DATA_CACHE
from web.catalog import latest_sync_run, load_playlist_dataset, load_selection

router = APIRouter()

@router.get("/api/nav-state")
def nav_state(request: Request):

    sp = get_spotify_client(request)
    if not sp:
        return {
            "build_status": "idle",
            "has_selection": False,
            "breakdown_source": None
        }

    from web.spotify_auth import get_user_id
    user_id = get_user_id(request)

    sync = latest_sync_run(user_id)
    build_status = sync["status"] if sync else "idle"

    selection = load_selection(user_id)
    selected_ids = selection["selected_ids"]
    breakdown_source = selection["breakdown_source"]

    user_cache = PLAYLIST_DATA_CACHE.get(user_id, {})
    loaded = all(
        pid in user_cache or load_playlist_dataset(user_id, pid)
        for pid in selected_ids
    )

    return {
        "build_status": build_status,
        "has_selection": bool(selected_ids),
        "has_playlist_data": loaded,
        "breakdown_source": breakdown_source
    }
