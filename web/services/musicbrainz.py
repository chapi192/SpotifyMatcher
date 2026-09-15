import re
import time
from urllib.parse import quote

import requests


BASE_URL = "https://musicbrainz.org/ws/2"
USER_AGENT = "WrappedNow/0.1 (personal local music organizer)"


def _lucene(value: str) -> str:
    return re.sub(r'([+\-&|!(){}\[\]^"~*?:\\/])', r'\\\1', value or "").strip()


def _candidate(recording: dict) -> dict:
    credits = recording.get("artist-credit") or []
    artists = "".join(
        item.get("name", "") + item.get("joinphrase", "")
        for item in credits if isinstance(item, dict)
    )
    return {
        "recording_id": recording.get("id"),
        "title": recording.get("title"),
        "artists": artists,
        "duration_ms": recording.get("length"),
        "score": int(recording.get("score") or 0),
    }


def match_recording(track: dict, session=requests) -> dict:
    if track.get("isrc"):
        url = f"{BASE_URL}/isrc/{quote(track['isrc'])}"
        method = "isrc"
    else:
        parts = [f'recording:"{_lucene(track.get("name"))}"']
        if track.get("artists"):
            parts.append(f'artist:"{_lucene(track["artists"].split(",")[0])}"')
        query = " AND ".join(parts)
        url = f"{BASE_URL}/recording?query={quote(query)}&limit=5"
        method = "metadata"

    response = session.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    recordings = payload.get("recordings") or []
    candidates = [_candidate(item) for item in recordings[:5]]
    if not candidates:
        return {"status": "missing", "method": method, "recording_id": None, "confidence": None, "candidates": []}

    best = candidates[0]
    score = 100 if method == "isrc" and len(candidates) == 1 else best["score"]
    expected_duration = track.get("duration_ms")
    actual_duration = best.get("duration_ms")
    if expected_duration and actual_duration:
        difference = abs(expected_duration - actual_duration)
        if difference > 10000:
            score -= 20
        elif difference > 5000:
            score -= 8

    status = "matched" if score >= 90 else "review"
    return {
        "status": status,
        "method": method,
        "recording_id": best["recording_id"] if status == "matched" else None,
        "confidence": max(0, min(score, 100)) / 100,
        "candidates": candidates,
    }


def respectful_pause() -> None:
    time.sleep(1.05)
