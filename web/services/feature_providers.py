import re

import requests


def _get(url: str, **kwargs):
    response = requests.get(url, timeout=30, **kwargs)
    response.raise_for_status()
    return response.json()


def _get_optional(url: str, **kwargs):
    response = requests.get(url, timeout=30, **kwargs)
    if response.status_code == 404:
        return {}
    response.raise_for_status()
    return response.json()


def acousticbrainz(track: dict) -> list[dict]:
    mbid = track["musicbrainz_recording_id"]
    high = _get_optional(f"https://acousticbrainz.org/api/v1/{mbid}/high-level").get("highlevel", {})
    low = _get_optional(f"https://acousticbrainz.org/api/v1/{mbid}/low-level")
    observations = []
    for name in (
        "danceability", "mood_acoustic", "mood_aggressive", "mood_electronic",
        "mood_happy", "mood_party", "mood_relaxed", "mood_sad",
        "voice_instrumental", "tonal_atonal",
    ):
        item = high.get(name)
        if item:
            observations.append({"name": name, "value": item.get("value"), "confidence": item.get("probability")})
    rhythm = low.get("rhythm", {})
    tonal = low.get("tonal", {})
    lowlevel = low.get("lowlevel", {})
    for name, value in (
        ("bpm", rhythm.get("bpm")), ("danceability_score", rhythm.get("danceability")),
        ("key", tonal.get("key_key")), ("scale", tonal.get("key_scale")),
        ("average_loudness", lowlevel.get("average_loudness")),
        ("dynamic_complexity", lowlevel.get("dynamic_complexity")),
    ):
        if value is not None:
            observations.append({"name": name, "value": value})
    return observations


def listenbrainz(track: dict) -> list[dict]:
    mbid = track["musicbrainz_recording_id"]
    payload = _get(
        "https://api.listenbrainz.org/1/metadata/recording/",
        params={"recording_mbids": mbid, "inc": "artist tag release"},
    ).get(mbid, {})
    tags = {}
    for group, values in (payload.get("tag") or {}).items():
        for tag in values or []:
            name = tag.get("tag")
            if name:
                tags[name] = max(tags.get(name, 0), int(tag.get("count") or 0))
    recording = payload.get("recording") or {}
    observations = [{"name": "tags", "value": [
        {"name": name, "count": count} for name, count in sorted(tags.items(), key=lambda item: (-item[1], item[0]))
    ]}]
    if recording.get("first_release_date"):
        observations.append({"name": "first_release_date", "value": recording["first_release_date"]})
    if recording.get("isrcs"):
        observations.append({"name": "isrcs", "value": recording["isrcs"]})
    return observations


def _plain(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def reccobeats(track: dict) -> list[dict]:
    search = _get(
        "https://api.reccobeats.com/v1/track/search",
        params={"searchText": f'{track["name"]} {track["artists"]}'},
    )
    expected_title = _plain(track["name"])
    expected_artist = _plain(track["artists"].split(",")[0])
    matches = []
    for candidate in search.get("content") or []:
        title = _plain(candidate.get("trackTitle"))
        artists = [_plain(item.get("name")) for item in candidate.get("artists") or []]
        duration = candidate.get("durationMs")
        duration_ok = not duration or not track.get("duration_ms") or abs(duration - track["duration_ms"]) <= 5000
        if title == expected_title and expected_artist in artists and duration_ok:
            matches.append(candidate)
    if not matches:
        return []
    payload = _get(f'https://api.reccobeats.com/v1/track/{matches[0]["id"]}/audio-features')
    if "content" in payload and isinstance(payload["content"], dict):
        payload = payload["content"]
    wanted = (
        "acousticness", "danceability", "energy", "instrumentalness", "liveness",
        "loudness", "speechiness", "tempo", "valence", "key", "mode",
    )
    return [{"name": name, "value": payload[name]} for name in wanted if payload.get(name) is not None]


PROVIDERS = {
    "acousticbrainz": acousticbrainz,
    "listenbrainz": listenbrainz,
    "reccobeats": reccobeats,
}
