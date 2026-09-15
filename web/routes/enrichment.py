import threading
import traceback

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from web.catalog import (
    begin_enrichment_job,
    enrichment_candidates,
    enrichment_status,
    finish_enrichment_job,
    save_track_identity,
    update_enrichment_job,
)
from web.services.musicbrainz import match_recording, respectful_pause
from web.spotify_auth import get_user_id


router = APIRouter()


def _run_musicbrainz_job(job_id: int, user_id: str) -> None:
    completed = matched = review = missing = 0
    try:
        candidates = enrichment_candidates(user_id)
        for index, track in enumerate(candidates):
            update_enrichment_job(job_id, current_track=track["name"] or track["track_id"])
            result = match_recording(track)
            save_track_identity(
                track["track_id"], recording_id=result["recording_id"],
                status=result["status"], method=result["method"],
                confidence=result["confidence"], candidates=result["candidates"],
            )
            completed += 1
            matched += int(result["status"] == "matched")
            review += int(result["status"] == "review")
            missing += int(result["status"] == "missing")
            update_enrichment_job(
                job_id, completed_tracks=completed, matched_tracks=matched,
                review_tracks=review, missing_tracks=missing,
            )
            if index < len(candidates) - 1:
                respectful_pause()
        finish_enrichment_job(job_id, "complete")
    except Exception as exc:
        traceback.print_exc()
        finish_enrichment_job(job_id, "error", str(exc)[:1000])


def _authenticated_user(request: Request):
    if not request.session.get("token_info"):
        return None
    return get_user_id(request)


@router.post("/api/enrichment/musicbrainz")
def start_musicbrainz_enrichment(request: Request):
    user_id = _authenticated_user(request)
    if not user_id:
        return JSONResponse({"error": "Not logged in"}, status_code=401)
    job_id = begin_enrichment_job(user_id, "musicbrainz")
    if job_id is None:
        return JSONResponse({"error": "MusicBrainz matching is already running"}, status_code=409)
    worker = threading.Thread(
        target=_run_musicbrainz_job, args=(job_id, user_id), daemon=True,
        name=f"musicbrainz-enrichment-{job_id}",
    )
    worker.start()
    return {"status": "started", "job_id": job_id}


@router.get("/api/enrichment/status")
def get_enrichment_status(request: Request):
    user_id = _authenticated_user(request)
    if not user_id:
        return JSONResponse({"error": "Not logged in"}, status_code=401)
    return enrichment_status(user_id)
