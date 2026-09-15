import threading
import traceback

import spotipy
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from web.catalog import (
    begin_sync_run,
    finish_sync_run,
    latest_sync_run,
    load_artist_cache,
    load_playlist_dataset,
    playlist_snapshot_matches,
    refresh_playlist_metadata,
    save_playlist_dataset,
    set_active_playlists,
    sync_history,
    update_sync_run,
)
from web.services.fetch_data import fetch_single_playlist
from web.services.profile_library import build_playlist_profiles
from web.spotify_auth import build_oauth, get_spotify_client, get_user_id
from web.state import ARTIST_CACHE, PLAYLIST_CACHE, PLAYLIST_DATA_CACHE


router = APIRouter()


def _playlist_track_total(playlist: dict) -> int:
    container = playlist.get("items") or playlist.get("tracks") or {}
    return int(container.get("total") or 0)


def _playlist_record(playlist: dict, user_id: str) -> dict:
    owner_id = (playlist.get("owner") or {}).get("id")
    return {
        "id": playlist.get("id"),
        "name": playlist.get("name") or "Untitled playlist",
        "track_count": _playlist_track_total(playlist),
        "image": (playlist.get("images") or [{}])[0].get("url"),
        "is_owner": owner_id == user_id,
        "owner_id": owner_id,
        "collaborative": bool(playlist.get("collaborative")),
        "snapshot_id": playlist.get("snapshot_id"),
        "is_liked": False,
    }


def _fetch_sync_targets(sp, user_id: str) -> list[dict]:
    targets = []
    results = sp.current_user_playlists(limit=50)

    while True:
        for playlist in results.get("items") or []:
            record = _playlist_record(playlist, user_id)
            if not record["id"]:
                continue
            if record["is_owner"] or record["collaborative"]:
                targets.append(record)
        if not results.get("next"):
            break
        results = sp.next(results)

    liked = sp.current_user_saved_tracks(limit=1)
    targets.append({
        "id": "__liked__",
        "name": "Liked Songs",
        "track_count": int(liked.get("total") or 0),
        "image": None,
        "is_owner": True,
        "owner_id": user_id,
        "collaborative": False,
        "snapshot_id": None,
        "is_liked": True,
    })
    return targets


def _run_sync(run_id: int, user_id: str, token_info: dict) -> None:
    try:
        oauth = build_oauth(None, token_info=token_info)
        sp = spotipy.Spotify(auth_manager=oauth, requests_timeout=30, retries=2)
        targets = _fetch_sync_targets(sp, user_id)
        removals = set_active_playlists(user_id, [target["id"] for target in targets])
        update_sync_run(run_id, total_playlists=len(targets), **removals)

        artist_cache = load_artist_cache()
        ARTIST_CACHE[user_id] = artist_cache
        completed = 0
        skipped = 0
        tracks_processed = 0
        new_playlists = 0
        changed_playlists = 0
        added_tracks = 0
        removed_tracks = removals["removed_tracks"]

        PLAYLIST_CACHE[user_id] = {
            "data": targets,
            "fetched_at": 0,
        }

        for target in targets:
            playlist_id = target["id"]
            update_sync_run(run_id, current_playlist=target["name"])

            if playlist_snapshot_matches(user_id, playlist_id, target["snapshot_id"]):
                refresh_playlist_metadata(user_id, target)
                persisted = load_playlist_dataset(user_id, playlist_id)
                if persisted:
                    profile = build_playlist_profiles({playlist_id: persisted}).get(playlist_id)
                    PLAYLIST_DATA_CACHE.setdefault(user_id, {})[playlist_id] = {
                        "dataset": persisted,
                        "profile": profile,
                        "fetched_at": 0,
                    }
                completed += 1
                skipped += 1
                update_sync_run(
                    run_id,
                    completed_playlists=completed,
                    skipped_playlists=skipped,
                    tracks_processed=tracks_processed,
                )
                continue

            def progress(amount: int) -> None:
                nonlocal tracks_processed
                tracks_processed += amount
                update_sync_run(run_id, tracks_processed=tracks_processed)

            dataset = fetch_single_playlist(
                sp,
                playlist_id,
                artist_cache=artist_cache,
                progress_callback=progress,
            )
            profile = build_playlist_profiles({playlist_id: dataset}).get(playlist_id)
            metadata = {
                "owner_id": target["owner_id"],
                "collaborative": target["collaborative"],
                "snapshot_id": target["snapshot_id"],
                "is_liked": target["is_liked"],
            }
            changes = save_playlist_dataset(user_id, dataset, metadata=metadata)
            if changes["is_new"]:
                new_playlists += 1
            elif changes["changed"]:
                changed_playlists += 1
            else:
                skipped += 1
            added_tracks += changes["added_tracks"]
            removed_tracks += changes["removed_tracks"]
            PLAYLIST_DATA_CACHE.setdefault(user_id, {})[playlist_id] = {
                "dataset": dataset,
                "profile": profile,
                "fetched_at": 0,
            }

            completed += 1
            update_sync_run(
                run_id,
                completed_playlists=completed,
                skipped_playlists=skipped,
                tracks_processed=tracks_processed,
                new_playlists=new_playlists,
                changed_playlists=changed_playlists,
                added_tracks=added_tracks,
                removed_tracks=removed_tracks,
            )

        finish_sync_run(run_id, "complete")
    except Exception as exc:
        traceback.print_exc()
        finish_sync_run(run_id, "error", error=str(exc)[:1000])


@router.post("/api/sync")
def start_sync(request: Request):
    sp = get_spotify_client(request)
    if not sp:
        return JSONResponse({"error": "Not logged in"}, status_code=401)

    user_id = get_user_id(request)
    token_info = request.session.get("token_info") or {}
    if not user_id or not token_info.get("access_token"):
        return JSONResponse({"error": "Spotify session is incomplete"}, status_code=401)

    run_id = begin_sync_run(user_id)
    if run_id is None:
        current = latest_sync_run(user_id)
        return JSONResponse(
            {"status": "already_running", "sync": current},
            status_code=409,
        )

    worker = threading.Thread(
        target=_run_sync,
        args=(run_id, user_id, token_info),
        daemon=True,
        name=f"spotify-sync-{run_id}",
    )
    worker.start()
    return {"status": "started", "run_id": run_id}


@router.get("/api/sync/status")
def sync_status(request: Request):
    if not request.session.get("token_info"):
        return JSONResponse({"error": "Not logged in"}, status_code=401)
    user_id = get_user_id(request)
    sync = latest_sync_run(user_id) if user_id else None
    return {"status": sync["status"] if sync else "never", "sync": sync}


@router.get("/api/sync/history")
def get_sync_history(request: Request, limit: int = 10):
    if not request.session.get("token_info"):
        return JSONResponse({"error": "Not logged in"}, status_code=401)
    user_id = get_user_id(request)
    return {"syncs": sync_history(user_id, limit) if user_id else []}
