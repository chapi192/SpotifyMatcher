import threading
import traceback

import requests

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from web.catalog import (
    begin_enrichment_job,
    begin_feature_enrichment_job,
    enrichment_candidates,
    enrichment_status,
    feature_comparison,
    feature_enrichment_candidates,
    finish_enrichment_job,
    save_track_identity,
    save_provider_result,
    update_enrichment_job,
)
from web.services.musicbrainz import match_recording, respectful_pause
from web.services.feature_providers import PROVIDERS
from web.spotify_auth import get_user_id


router = APIRouter()


def _run_musicbrainz_job(job_id: int, user_id: str, batch_limit: int) -> None:
    completed = matched = review = missing = failed = 0
    try:
        candidates = enrichment_candidates(user_id, batch_limit)
        for index, track in enumerate(candidates):
            update_enrichment_job(job_id, current_track=track["name"] or track["track_id"])
            try:
                result = match_recording(track)
            except requests.RequestException:
                result = {
                    "recording_id": None, "status": "error", "method": "isrc" if track.get("isrc") else "metadata",
                    "confidence": None, "candidates": [],
                    "reason": "MusicBrainz remained temporarily unavailable after four attempts. This track is safe to retry.",
                }
            save_track_identity(
                track["track_id"], recording_id=result["recording_id"],
                status=result["status"], method=result["method"],
                confidence=result["confidence"], candidates=result["candidates"],
                reason=result["reason"],
            )
            completed += 1
            matched += int(result["status"] == "matched")
            review += int(result["status"] == "review")
            missing += int(result["status"] == "missing")
            failed += int(result["status"] == "error")
            update_enrichment_job(
                job_id, completed_tracks=completed, matched_tracks=matched,
                review_tracks=review, missing_tracks=missing, failed_tracks=failed,
            )
            if index < len(candidates) - 1:
                respectful_pause()
        finish_enrichment_job(job_id, "complete")
    except Exception as exc:
        traceback.print_exc()
        finish_enrichment_job(job_id, "error", str(exc)[:1000])


def _run_feature_job(job_id: int, user_id: str, provider: str, batch_limit: int) -> None:
    completed = found = missing = failed = 0
    try:
        for track in feature_enrichment_candidates(user_id, provider, batch_limit):
            update_enrichment_job(job_id, current_track=track["name"] or track["track_id"])
            try:
                observations = PROVIDERS[provider](track)
                status = "complete" if observations else "missing"
                reason = None if observations else f"{provider.title()} returned no sufficiently reliable data for this recording."
            except requests.HTTPError as exc:
                observations = []
                if exc.response is not None and exc.response.status_code == 404:
                    status, reason = "missing", f"{provider.title()} has no entry for this recording."
                else:
                    status, reason = "error", f"{provider.title()} was temporarily unavailable. This track is safe to retry."
            except requests.RequestException:
                observations, status = [], "error"
                reason = f"{provider.title()} was temporarily unavailable. This track is safe to retry."
            save_provider_result(track["track_id"], provider, status, observations, reason)
            completed += 1
            found += int(status == "complete")
            missing += int(status == "missing")
            failed += int(status == "error")
            update_enrichment_job(
                job_id, completed_tracks=completed, matched_tracks=found,
                missing_tracks=missing, failed_tracks=failed,
            )
        finish_enrichment_job(job_id, "complete")
    except Exception as exc:
        traceback.print_exc()
        finish_enrichment_job(job_id, "error", str(exc)[:1000])


def _authenticated_user(request: Request):
    if not request.session.get("token_info"):
        return None
    return get_user_id(request)


@router.post("/api/enrichment/musicbrainz")
def start_musicbrainz_enrichment(request: Request, data: dict = Body(default={})):
    user_id = _authenticated_user(request)
    if not user_id:
        return JSONResponse({"error": "Not logged in"}, status_code=401)
    try:
        batch_limit = max(1, min(int(data.get("limit", 25)), 100))
    except (TypeError, ValueError):
        return JSONResponse({"error": "Batch size must be a number from 1 to 100"}, status_code=400)
    job_id = begin_enrichment_job(user_id, "musicbrainz", batch_limit)
    if job_id is None:
        return JSONResponse({"error": "MusicBrainz matching is already running"}, status_code=409)
    worker = threading.Thread(
        target=_run_musicbrainz_job, args=(job_id, user_id, batch_limit), daemon=True,
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


@router.post("/api/enrichment/features/{provider}")
def start_feature_enrichment(provider: str, request: Request, data: dict = Body(default={})):
    user_id = _authenticated_user(request)
    if not user_id:
        return JSONResponse({"error": "Not logged in"}, status_code=401)
    if provider not in PROVIDERS:
        return JSONResponse({"error": "Unknown enrichment provider"}, status_code=404)
    try:
        batch_limit = max(1, min(int(data.get("limit", 25)), 100))
    except (TypeError, ValueError):
        return JSONResponse({"error": "Batch size must be a number from 1 to 100"}, status_code=400)
    job_id = begin_feature_enrichment_job(user_id, provider, batch_limit)
    if job_id is None:
        return JSONResponse({"error": f"{provider} enrichment is already running"}, status_code=409)
    threading.Thread(
        target=_run_feature_job, args=(job_id, user_id, provider, batch_limit),
        daemon=True, name=f"{provider}-enrichment-{job_id}",
    ).start()
    return {"status": "started", "job_id": job_id}


@router.get("/api/enrichment/features")
def get_feature_comparison(request: Request, limit: int = 100):
    user_id = _authenticated_user(request)
    if not user_id:
        return JSONResponse({"error": "Not logged in"}, status_code=401)
    return {"tracks": feature_comparison(user_id, limit)}
