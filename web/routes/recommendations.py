from fastapi import APIRouter, Request, Query
from web.spotify_auth import get_spotify_client
from web.routes.library import get_active_dataset_and_profiles

router = APIRouter()

# ------------------------------------------------------------
# Build Playlist Profile
# ------------------------------------------------------------

def build_playlist_profile(tracks):

    artists = {}
    genres = {}
    albums = {}
    decades = {}

    for track in tracks:

        # -------- Artists + Genres --------

        for artist in track.get("artists", []):

            name = artist.get("artist_name")

            if name:
                artists[name] = artists.get(name, 0) + 1

            for g in artist.get("genres", []):
                genres[g] = genres.get(g, 0) + 1

        # -------- Album --------

        album_name = track.get("album", {}).get("album_name")

        if album_name:
            albums[album_name] = albums.get(album_name, 0) + 1

        # -------- Decade --------

        release_date = track.get("album", {}).get("release_date")

        if release_date and len(release_date) >= 4:
            try:
                year = int(release_date[:4])
                decade = (year // 10) * 10
                decades[decade] = decades.get(decade, 0) + 1
            except:
                pass

    return {
        "artists": artists,
        "genres": genres,
        "albums": albums,
        "decades": decades
    }


# ------------------------------------------------------------
# Compare Track to Playlist Profile
# ------------------------------------------------------------

def evaluate_track(track, profile):

    artist_matches = []

    for artist in track.get("artists", []):
        name = artist.get("artist_name")

        if name in profile["artists"]:
            artist_matches.append(name)

    genre_matches = []

    for artist in track.get("artists", []):
        for g in artist.get("genres", []):
            if g in profile["genres"]:
                genre_matches.append(g)

    genre_matches = list(set(genre_matches))

    album_name = track.get("album", {}).get("album_name")
    album_match = album_name in profile["albums"]

    decade_match = False

    release_date = track.get("album", {}).get("release_date")

    if release_date and len(release_date) >= 4:
        try:
            year = int(release_date[:4])
            decade = (year // 10) * 10
            decade_match = decade in profile["decades"]
        except:
            pass

    return {
        "artistMatch": artist_matches,
        "genreMatches": genre_matches,
        "albumMatch": album_match,
        "decadeMatch": decade_match
    }


def score_playlist_match(signals, weights):

    score = 0
    reasons = []

    if signals["artistMatch"] and weights["artist"] > 0:
        score += weights["artist"]
        reasons.append("artist")

    if signals["genreMatches"] and weights["genre"] > 0:
        score += weights["genre"] * len(signals["genreMatches"])
        reasons.append("genre")

    if signals["albumMatch"] and weights["album"] > 0:
        score += weights["album"]
        reasons.append("album")

    if signals["decadeMatch"] and weights["decade"] > 0:
        score += weights["decade"]
        reasons.append("decade")

    return score, reasons


# ------------------------------------------------------------
# Recommendation Engine
# ------------------------------------------------------------

@router.get("/api/recommendation-breakdown")
def recommendation_breakdown(
    request: Request,
    artist: int = Query(3),
    genre: int = Query(3),
    album: int = Query(1),
    decade: int = Query(1)
):

    sp = get_spotify_client(request)
    if not sp:
        return {"status": "error", "message": "Not logged in"}

    dataset, _profiles, err = get_active_dataset_and_profiles(request, sp)
    if err:
        return err

    playlist_ids = list(dataset.keys())

    if len(playlist_ids) < 2:
        return {"status": "error", "message": "Need at least two playlists"}

    # ---------------------------------
    # Track membership lookup
    # ---------------------------------

    track_membership = {}

    for pid, playlist in dataset.items():
        for track in playlist.get("tracks", []):
            tid = track.get("track_id")
            if not tid:
                continue
            track_membership.setdefault(tid, set()).add(pid)

    # ---------------------------------
    # Playlist selection
    # ---------------------------------

    breakdown_id = request.session.get("breakdown_source")

    if not breakdown_id:
        return {
            "status": "error",
            "message": "No breakdown playlist selected"
        }

    if breakdown_id not in dataset:
        return {
            "status": "error",
            "message": "Breakdown playlist not in selected playlists"
        }

    target_ids = [
        pid for pid in dataset.keys()
        if pid != breakdown_id
    ]

    breakdown_tracks = dataset[breakdown_id]["tracks"]
    breakdown_name = dataset[breakdown_id]["playlist_name"]

    targets = {
        pid: dataset[pid]["playlist_name"]
        for pid in target_ids
    }

    # ---------------------------------
    # Build profiles
    # ---------------------------------

    profiles = {}

    for pid in target_ids:
        tracks = dataset[pid]["tracks"]
        profiles[pid] = build_playlist_profile(tracks)

    results = []

    max_recommendations = min(3, len(target_ids))

    # ---------------------------------
    # Evaluate tracks
    # ---------------------------------

    for track in breakdown_tracks:

        playlist_scores = []

        for pid, profile in profiles.items():

            if pid in track_membership.get(track.get("track_id"), set()):
                continue

            signals = evaluate_track(track, profile)

            weights = {
                "artist": int(artist),
                "genre": int(genre),
                "album": int(album),
                "decade": int(decade)
            }

            score, reasons = score_playlist_match(signals, weights)

            playlist_scores.append({
                "playlist_id": pid,
                "playlist_name": targets[pid],
                "score": score,
                "reasons": reasons,
                "signals": signals
            })

        playlist_scores.sort(key=lambda x: x["score"], reverse=True)

        top_matches = playlist_scores[:max_recommendations]

        # ---- debug metadata ----

        artist_names = []
        artist_genres = []

        for a in track.get("artists") or []:
            if not isinstance(a, dict):
                continue

            name = a.get("artist_name")
            if name:
                artist_names.append(name)

            for g in a.get("genres") or []:
                artist_genres.append(g)

        album_info = track.get("album") or {}

        results.append({
            "track_name": track.get("track_name"),
            "track_id": track.get("track_id"),
            "artists": artist_names,
            "genres": list(set(artist_genres)),
            "album_name": album_info.get("album_name"),
            "release_date": album_info.get("release_date"),
            "recommendations": top_matches
        })

    return {
        "status": "ready",
        "data": {
            "breakdown_playlist": {
                "id": breakdown_id,
                "name": breakdown_name
            },
            "targets": targets,
            "tracks": results
        }
    }


# ------------------------------------------------------------
# Debug Profiles
# ------------------------------------------------------------

@router.get("/api/recommendation-profiles")
def recommendation_profiles(request: Request):

    sp = get_spotify_client(request)
    if not sp:
        return {"status": "error", "message": "Not logged in"}

    dataset, _profiles, err = get_active_dataset_and_profiles(request, sp)
    if err:
        return err

    profiles = {}

    for pid, playlist in dataset.items():
        profiles[pid] = build_playlist_profile(playlist["tracks"])

    return {
        "status": "ready",
        "data": profiles
    }


@router.get("/api/recommendation-debug-sample")
def recommendation_debug_sample(request: Request):

    sp = get_spotify_client(request)
    if not sp:
        return {"status": "error", "message": "Not logged in"}

    dataset, _profiles, err = get_active_dataset_and_profiles(request, sp)
    if err:
        return err

    breakdown_id = request.session.get("breakdown_source")

    if not breakdown_id or breakdown_id not in dataset:
        return {"status": "error", "message": "Bad breakdown selection"}

    tracks = dataset[breakdown_id].get("tracks", [])

    if not tracks:
        return {"status": "error", "message": "No tracks in breakdown playlist"}

    t = tracks[0]

    return {
        "status": "ready",
        "data": {
            "track_keys": sorted(list(t.keys())),
            "track_id": t.get("track_id"),
            "track_name": t.get("track_name"),
            "artists": t.get("artists"),
            "album": t.get("album"),
        }
    }