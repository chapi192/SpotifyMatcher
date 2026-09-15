import re
import time
from urllib.parse import quote

import requests


BASE_URL = "https://musicbrainz.org/ws/2"
USER_AGENT = "WrappedNow/0.1 (personal local music organizer)"
MAX_ATTEMPTS = 4


def _lucene(value: str) -> str:
    return re.sub(r'([+\-&|!(){}\[\]^"~*?:\\/])', r'\\\1', value or "").strip()


def _search_title(value: str) -> str:
    value = (value or "").strip().strip('"“”')
    value = re.sub(
        r"\s*[-–—]\s*(?:\d{4}\s+)?(?:re)?master(?:ed)?(?:\s+version)?\s*$",
        "", value, flags=re.IGNORECASE,
    )
    value = re.sub(
        r"\s*\((?:\d{4}\s+)?(?:re)?master(?:ed)?(?:\s+version)?\)\s*$",
        "", value, flags=re.IGNORECASE,
    )
    return value.strip().strip('"“”')


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
        parts = [f'recording:"{_lucene(_search_title(track.get("name")))}"']
        if track.get("artists"):
            parts.append(f'artist:"{_lucene(track["artists"].split(",")[0])}"')
        query = " AND ".join(parts)
        url = f"{BASE_URL}/recording?query={quote(query)}&limit=5"
        method = "metadata"

    response = None
    for attempt in range(MAX_ATTEMPTS):
        response = session.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=20,
        )
        if response.status_code not in {429, 503}:
            break
        if attempt < MAX_ATTEMPTS - 1:
            retry_after = response.headers.get("Retry-After")
            try:
                delay = float(retry_after) if retry_after else 2 ** attempt
            except (TypeError, ValueError):
                delay = 2 ** attempt
            time.sleep(min(max(delay, 1.05), 30))
    response.raise_for_status()
    payload = response.json()
    recordings = payload.get("recordings") or []
    candidates = [_candidate(item) for item in recordings[:5]]
    if not candidates:
        return {
            "status": "missing", "method": method, "recording_id": None,
            "confidence": None, "candidates": [],
            "reason": "MusicBrainz returned no recording for the normalized title and artist.",
        }

    expected_duration = track.get("duration_ms")
    def adjusted_score(candidate: dict) -> int:
        score = 100 if method == "isrc" else candidate["score"]
        actual_duration = candidate.get("duration_ms")
        if not expected_duration or not actual_duration:
            return score
        difference = abs(expected_duration - actual_duration)
        if difference > 10000:
            score -= 20
        elif difference > 5000:
            score -= 8
        return score

    candidates.sort(key=adjusted_score, reverse=True)
    best = candidates[0]
    score = adjusted_score(best)

    status = "matched" if score >= 90 else "review"
    best_duration = best.get("duration_ms")
    duration_difference = abs(expected_duration - best_duration) if expected_duration and best_duration else None
    if status == "matched":
        reason = "Accepted because the identity score and recording duration passed the confidence threshold."
    elif duration_difference and duration_difference > 10000:
        reason = f"Held for review because the closest candidate is {round(duration_difference / 1000)} seconds different in length."
    else:
        reason = f"Held for review because the best candidate scored {max(0, min(score, 100))}%, below the 90% automatic-match threshold."
    return {
        "status": status,
        "method": method,
        "recording_id": best["recording_id"] if status == "matched" else None,
        "confidence": max(0, min(score, 100)) / 100,
        "candidates": candidates,
        "reason": reason,
    }


def respectful_pause() -> None:
    time.sleep(1.05)
