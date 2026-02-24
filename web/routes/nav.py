from fastapi import APIRouter, Request

from web.spotify_auth import get_spotify_client, build_oauth
from web.state import USER_BUILD_STATE

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
    state = USER_BUILD_STATE.get(user_id)

    build_status = state["status"] if state else "idle"

    selected_ids = request.session.get("selected_playlists", [])
    breakdown_source = request.session.get("breakdown_source")

    return {
        "build_status": build_status,
        "has_selection": bool(selected_ids),
        "breakdown_source": breakdown_source
    }