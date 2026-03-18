import traceback
from fastapi import APIRouter, Request
import threading
import time
import spotipy
from web.utils.debug import build_debug
from web.spotify_auth import get_spotify_client, build_oauth
from web.state import BUILD_STATE, PLAYLIST_CACHE, USER_BUILD_STATE, PLAYLIST_DATA_CACHE, ARTIST_CACHE
from web.services.fetch_data import fetch_single_playlist
from web.services.profile_library import build_playlist_profiles

router = APIRouter()

def start_incremental_build(request: Request, user_id: str, version: int):

    token_info = request.session.get("token_info")
    if not token_info:
        return

    oauth = build_oauth(request)
    oauth.token_info = token_info

    sp = get_spotify_client(request)
    if not sp:
        return

    def run_job():
        try:

            build_debug(f"Build worker started → version {version}")

            thread_sp = spotipy.Spotify(auth_manager=oauth)
            artist_cache = ARTIST_CACHE.setdefault(user_id, {})

            build_start_time = time.time()

            while True:

                state = USER_BUILD_STATE.get(user_id)

                if not state or state.get("version") != version or state.get("status") != "building":
                    build_debug("Build cancelled due to version change")
                    return

                if not state:
                    build_debug("Build state missing, exiting worker")
                    return

                state = USER_BUILD_STATE.get(user_id)

                playlist_map = state.get("playlist_track_map", {})

                pending = [
                    pid for pid in playlist_map
                    if pid not in PLAYLIST_DATA_CACHE.get(user_id, {})
                ]

                # If user removed everything, stop immediately
                if not playlist_map:
                    build_debug("No playlists remain in build — stopping worker")
                    return

                if not pending:

                    state = USER_BUILD_STATE.get(user_id)

                    if state and state.get("version") == version and state.get("status") == "building":
                        state["tracks_processed"] = state["total_tracks"]
                        state["status"] = "complete"

                    build_debug("Build finished — no pending playlists")

                    break

                pid = pending[0]

                state = USER_BUILD_STATE.get(user_id)

                if state and pid not in state.get("playlist_track_map", {}):
                    build_debug(f"Skipping removed playlist → {pid}")
                    continue

                playlist_start_time = time.time()

                build_debug(f"Loading playlist → {pid}")

                def progress_increment(amount):
                    state = USER_BUILD_STATE.get(user_id)
                    if not state:
                        return

                    if state.get("status") != "building":
                        return

                    if state.get("version") != version:
                        return

                    state["tracks_processed"] = min(
                        state["tracks_processed"] + amount,
                        state["total_tracks"]
                    )

                    build_debug(f"Progress → {state['tracks_processed']} / {state['total_tracks']}")

                def cancel_check():

                    state = USER_BUILD_STATE.get(user_id)

                    if not state:
                        return True

                    if state.get("status") != "building":
                        return True

                    if state["version"] != version:
                        return True

                    if pid not in state.get("playlist_track_map", {}):
                        return True

                    return False

                playlist_dataset = fetch_single_playlist(
                    thread_sp,
                    pid,
                    artist_cache=artist_cache,
                    progress_callback=progress_increment,
                    cancel_check=cancel_check
                )

                if playlist_dataset is None:
                    build_debug(f"Playlist cancelled mid-fetch → {pid}")
                    continue

                state = USER_BUILD_STATE.get(user_id)
                if not state or pid not in state.get("playlist_track_map", {}):
                    build_debug(f"Discarding playlist removed mid-load → {pid}")
                    continue

                playlist_duration = time.time() - playlist_start_time

                build_debug(f"Playlist loaded → {pid} ({playlist_duration:.2f}s)")

                single_dataset = {pid: playlist_dataset}
                profile = build_playlist_profiles(single_dataset).get(pid)

                PLAYLIST_DATA_CACHE.setdefault(user_id, {})
                PLAYLIST_DATA_CACHE[user_id][pid] = {
                    "dataset": playlist_dataset,
                    "profile": profile,
                    "fetched_at": time.time()
                }

            total_duration = time.time() - build_start_time
            build_debug(f"Build complete in {total_duration:.2f}s")

        except Exception as e:
            print("Incremental build error:", e)
            traceback.print_exc()

            state = USER_BUILD_STATE.get(user_id)
            if state and state["version"] == version:
                state["status"] = "error"

    threading.Thread(target=run_job, daemon=True).start()

@router.get("/api/build-progress")
def build_progress(request: Request):

    from web.spotify_auth import get_user_id, get_spotify_client

    user_id = get_user_id(request)

    # Fallback if session missing user_id
    if not user_id:
        sp = get_spotify_client(request)
        if not sp:
            return {"status": "idle"}
        user_id = sp.current_user()["id"]
        request.session["user_id"] = user_id

    state = USER_BUILD_STATE.get(user_id)

    build_debug(f"Progress request {state}")

    if not state:
        return {"status": "idle"}

    status = state.get("status")

    if status == "complete":
        return {"status": "complete"}

    if status == "error":
        return {"status": "error"}

    if status == "cancelled":
        return {"status": "idle"}

    if status != "building":
        return {"status": "idle"}

    return {
        "status": "building",
        "total_tracks": state.get("total_tracks", 0),
        "tracks_processed": state.get("tracks_processed", 0),
        "loaded_tracks": state.get("tracks_processed", 0)
    }