from fastapi import APIRouter, Request
import threading
import time
import spotipy

from web.spotify_auth import get_spotify_client, build_oauth, build_oauth
from web.state import BUILD_STATE, USER_BUILD_STATE, PLAYLIST_DATA_CACHE
from web.services.fetch_data import fetch_single_playlist
from web.services.profile_library import build_playlist_profiles

router = APIRouter()

def start_incremental_build(request: Request, user_id: str, version: int, playlist_ids: list):

    token_info = request.session.get("token_info")
    if not token_info:
        return

    oauth = build_oauth()
    oauth.token_info = token_info

    sp = get_spotify_client(request)
    if not sp:
        return

    def run_job():
        try:
            thread_sp = spotipy.Spotify(auth_manager=oauth)
            artist_cache = {}

            for pid in playlist_ids:

                if BUILD_STATE.get(user_id, {}).get("version") != version:
                    return
                    
                def progress_increment(amount):
                    state = USER_BUILD_STATE.get(user_id)
                    if not state:
                        return
                    if state["version"] != version:
                        return
                    state["tracks_processed"] = min(
                        state["tracks_processed"] + amount,
                        state["total_tracks"]
                    )

                playlist_dataset = fetch_single_playlist(
                    thread_sp,
                    pid,
                    artist_cache=artist_cache,
                    progress_callback=progress_increment
)

                single_dataset = {pid: playlist_dataset}
                profile = build_playlist_profiles(single_dataset).get(pid)

                PLAYLIST_DATA_CACHE.setdefault(user_id, {})
                PLAYLIST_DATA_CACHE[user_id][pid] = {
                    "dataset": playlist_dataset,
                    "profile": profile,
                    "fetched_at": time.time()
                }
            
            state = USER_BUILD_STATE.get(user_id)
            if state and state["version"] == version:
                state["tracks_processed"] = state["total_tracks"]
                state["status"] = "complete"

        except Exception as e:
            print("Incremental build error:", e)

            state = USER_BUILD_STATE.get(user_id)
            if state and state["version"] == version:
                state["status"] = "error"

    threading.Thread(target=run_job, daemon=True).start()

@router.get("/api/build-progress")
def build_progress(request: Request):

    sp = get_spotify_client(request)
    if not sp:
        return {"status": "idle"}

    user_id = sp.current_user()["id"]
    state = USER_BUILD_STATE.get(user_id)

    if not state:
        return {"status": "idle"}

    if state["status"] == "complete":
        return {"status": "complete"}

    if state["status"] == "error":
        return {"status": "error"}

    return {
        "status": "building",
        "total_tracks": state["total_tracks"],
        "tracks_processed": state["tracks_processed"]
    }