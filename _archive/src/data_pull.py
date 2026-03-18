# THIS SCRIPT PULLS DATA DIRECTLY FROM SPOTIFY USING YOUR ACCOUNT'S CREDENTIALS
# AND SAVES IT LOCALLY AS JSON FILES TO BE EDITED BY OTHER SCRIPTS.

import spotipy
import my_secrets
from spotipy.oauth2 import SpotifyOAuth
import json
from pathlib import Path
import time
import datetime
import sys
import spotipy.exceptions
from models import Track, Playlist


# =====================================================================
# DEBUG PRINT
# =====================================================================

debug = True

def Print(msg: str, level="info"):
    if not debug:
        return

    ts = datetime.datetime.now().strftime("%H:%M:%S")
    tag = {
        "info": "",
        "warn": "(!) ",
        "error": "[ERR] ",
        "success": ""
    }.get(level, "")

    msg = msg.replace("→", "->")
    print(f"{ts} {tag}{msg}")
    sys.stdout.flush()


def progress_bar(prefix, index, total, bar_length=25):
    if total <= 0:
        return
    frac = index / total
    filled = int(frac * bar_length)
    bar = "#" * filled + "-" * (bar_length - filled)
    print(f"\r{prefix[:22]:22} [{bar}] {index}/{total}", end="", flush=True)
    if index == total:
        print()


# =====================================================================
# SPOTIFY SAFE CALL
# =====================================================================

def safe_spotify_call(func, *args, **kwargs):
    """Retry Spotify API calls safely when hitting rate limits."""
    while True:
        try:
            return func(*args, **kwargs)
        except spotipy.exceptions.SpotifyException as e:
            if e.http_status == 429:
                retry_after = int(e.headers.get("Retry-After", 2))
                Print(f"Rate limit hit. Sleeping {retry_after} sec...", "warn")
                time.sleep(retry_after)
            else:
                raise


# =====================================================================
# PATHS
# =====================================================================

BASE_DIR = Path(__file__).resolve().parent.parent  # Exportify/
DATA_DIR = BASE_DIR / "data" / "raw"
CONFIG_DIR = BASE_DIR / "config"
CONFIG_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
SKIP_FILE = CONFIG_DIR / "skip_playlists.txt"


# =====================================================================
# SAVE / LOAD
# =====================================================================

def save_library_to_json(tracks: dict, playlists: dict):
    tracks_path = DATA_DIR / "tracks.json"
    playlists_path = DATA_DIR / "playlists.json"

    with tracks_path.open("w", encoding="utf-8") as f:
        json.dump({uri: t.to_dict() for uri, t in tracks.items()}, f, indent=4)

    with playlists_path.open("w", encoding="utf-8") as f:
        json.dump({pid: p.to_dict() for pid, p in playlists.items()}, f, indent=4)


def load_library_from_json():
    tracks_path = DATA_DIR / "tracks.json"
    playlists_path = DATA_DIR / "playlists.json"

    with tracks_path.open("r", encoding="utf-8") as f:
        raw_tracks = json.load(f)

    with playlists_path.open("r", encoding="utf-8") as f:
        raw_playlists = json.load(f)

    tracks = {uri: Track.from_dict(t) for uri, t in raw_tracks.items()}
    playlists = {pid: Playlist.from_dict(p) for pid, p in raw_playlists.items()}

    return tracks, playlists


def load_skip_list():
    if not SKIP_FILE.exists():
        return set()
    with SKIP_FILE.open("r", encoding="utf-8") as f:
        return {line.strip().lower() for line in f if line.strip()}


# =====================================================================
# PLAYLIST FETCHING
# =====================================================================

def get_all_playlists_and_counts(sp):
    Print("Fetching playlists...")
    playlists = sp.current_user_playlists()
    items = playlists["items"]

    while playlists["next"]:
        playlists = sp.next(playlists)
        items.extend(playlists["items"])

    playlist_objects = [
        Playlist(
            playlist_id=p["id"],
            name=p["name"],
            description=p.get("description", ""),
            owner=p["owner"]["display_name"],
            contained_tracks=[]
        )
        for p in items
    ]

    track_counts = {p["id"]: p["tracks"]["total"] for p in items}

    Print(f"Total playlists found: {len(playlist_objects)}")
    return playlist_objects, track_counts


def fetch_playlist_tracks(sp, playlist: Playlist, artist_genre_cache: dict):
    # first page
    raw = safe_spotify_call(sp.playlist_items, playlist.playlist_id)
    items = raw["items"]
    total = raw["total"]  # Spotify gives the total track count

    count = 0
    track_map = {}
    uris = []

    # Process first page
    for item in raw["items"]:
        count += 1
        progress_bar(playlist.name, count, total)

        t = item["track"]
        if not t:
            continue

        uri = t["uri"]
        uris.append(uri)
        track_map[uri] = t

    # Process remaining pages
    while raw["next"]:
        raw = safe_spotify_call(sp.next, raw)

        for item in raw["items"]:
            count += 1
            progress_bar(playlist.name, count, total)

            t = item["track"]
            if not t:
                continue

            uri = t["uri"]
            uris.append(uri)
            track_map[uri] = t

    playlist.contained_tracks = uris
    return track_map


# =====================================================================
# BATCH GENRE FETCHING
# =====================================================================

def fetch_genres_for_artists(sp, artist_ids: list[str], cache: dict):
    """Fetch genres for many artists at once (max 50 per request)."""
    missing = [aid for aid in artist_ids if aid not in cache]

    for i in range(0, len(missing), 50):
        batch = missing[i:i+50]
        result = safe_spotify_call(sp.artists, batch)
        for artist in result["artists"]:
            cache[artist["id"]] = artist.get("genres", [])


# =====================================================================
# UPDATE PLAYLIST / TRACKS
# =====================================================================

def update_tracks_and_playlist_for_changed(
    sp,
    playlist: Playlist,
    old_playlist: Playlist | None,
    tracks: dict,
    artist_genre_cache: dict
):

    old_uris = set(old_playlist.contained_tracks) if old_playlist else set()
    track_map = fetch_playlist_tracks(sp, playlist, artist_genre_cache)

    # Batch artist genre lookup
    artist_ids = [
        t["artists"][0]["id"]
        for t in track_map.values()
        if t["artists"]
    ]
    unique_ids = list(set(artist_ids))
    fetch_genres_for_artists(sp, unique_ids, artist_genre_cache)

    new_uris = set(playlist.contained_tracks)

    # Update or create tracks
    for uri in new_uris:
        t = track_map[uri]
        artist_id = t["artists"][0]["id"] if t["artists"] else None
        genres = artist_genre_cache.get(artist_id, [])

        if uri in tracks:
            track_obj = tracks[uri]
            track_obj.track_name = t["name"]
            track_obj.album_name = t["album"]["name"]
            track_obj.artist_names = [a["name"] for a in t["artists"]]
            track_obj.release_date = t["album"]["release_date"]
            track_obj.genres = genres
            track_obj.duration_ms = t["duration_ms"]
            track_obj.popularity = t["popularity"]
            track_obj.explicit = t["explicit"]
        else:
            track_obj = Track(
                track_uri=t["uri"],
                track_name=t["name"],
                album_name=t["album"]["name"],
                artist_names=[a["name"] for a in t["artists"]],
                release_date=t["album"]["release_date"],
                genres=genres,
                duration_ms=t["duration_ms"],
                popularity=t["popularity"],
                explicit=t["explicit"],
                associated_playlists=[]
            )
            tracks[uri] = track_obj

        # add association
        if playlist.playlist_id not in track_obj.associated_playlists:
            track_obj.associated_playlists.append(playlist.playlist_id)

    # remove any old associations
    removed_uris = old_uris - new_uris
    for uri in removed_uris:
        if uri in tracks:
            t = tracks[uri]
            if playlist.playlist_id in t.associated_playlists:
                t.associated_playlists.remove(playlist.playlist_id)


# =====================================================================
# MAIN
# =====================================================================

if __name__ == "__main__":

    sp = spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=my_secrets.CLIENT_ID,
            client_secret=my_secrets.CLIENT_SECRET,
            redirect_uri=my_secrets.REDIRECT_URI,
            scope="playlist-read-private playlist-read-collaborative user-library-read user-read-private",
            open_browser=True
        )
    )

    Print("Checking for existing saved data...")

    try:
        old_tracks, old_playlists = load_library_from_json()
        Print("Loaded existing library.")
    except FileNotFoundError:
        old_tracks, old_playlists = {}, {}
        Print("No existing library found. Starting fresh.", "warn")

    playlist_list, remote_track_counts = get_all_playlists_and_counts(sp)
    skip = load_skip_list()

    Print("")

    merged_playlists = old_playlists.copy()
    merged_tracks = old_tracks.copy()
    artist_genre_cache = {}

    # Process playlists
    for pl in playlist_list:
        if pl.name.lower() in skip:
            continue  # silent skip

        old_p = old_playlists.get(pl.playlist_id)
        remote_count = remote_track_counts.get(pl.playlist_id, 0)
        old_count = len(old_p.contained_tracks) if old_p else -1

        if old_p and remote_count == old_count:
            Print(f"{pl.name}: up-to-date ({remote_count} tracks)")
            merged_playlists[pl.playlist_id] = old_p
            continue

        Print(f"{pl.name}: updating ({remote_count} tracks)")
        update_tracks_and_playlist_for_changed(
            sp,
            pl,
            old_p,
            merged_tracks,
            artist_genre_cache
        )
        merged_playlists[pl.playlist_id] = pl

    # Clean skipped playlists from stored JSON
    playlists_to_remove = [
        pid for pid, pl in merged_playlists.items()
        if pl.name.lower() in skip
    ]

    for pid in playlists_to_remove:
        merged_playlists.pop(pid, None)

    for track in merged_tracks.values():
        track.associated_playlists = [
            pid for pid in track.associated_playlists
            if pid not in playlists_to_remove
        ]

    save_library_to_json(merged_tracks, merged_playlists)

    Print("")
    Print(f"Library saved: {len(merged_tracks)} tracks, {len(merged_playlists)} playlists.", "success")
    Print("Done.", "success")
