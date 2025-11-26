# THIS SCRIPT PULLS DATA DIRECTLY FROM SPOTIFY USING YOUR ACCOUNT'S CREDENTIALS
# AND SAVES IT LOCALLY AS JSON FILES.

import spotipy
import my_secrets
from spotipy.oauth2 import SpotifyOAuth
import json
from pathlib import Path
import time
import spotipy.exceptions

def safe_spotify_call(func, *args, **kwargs):
    """Retry Spotify API calls safely when hitting rate limits."""
    while True:
        try:
            return func(*args, **kwargs)
        except spotipy.exceptions.SpotifyException as e:
            if e.http_status == 429:
                retry_after = int(e.headers.get("Retry-After", 2))
                Print(f"Rate limit hit. Sleeping {retry_after} seconds...")
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
SKIP_FILE = CONFIG_DIR / "skip_playlists.txt"
DATA_DIR.mkdir(parents=True, exist_ok=True)

debug = True
def Print(msg: str):
    if debug:
        print(msg)

def progress_bar(prefix, index, total, bar_length=20):
    if total <= 0:
        return
    filled = int(bar_length * index / total)
    bar = "#" * filled + "-" * (bar_length - filled)
    print(f"\r{prefix}: [{bar}] {index}/{total}", end="", flush=True)


# =====================================================================
# SPOTIFY LOGIN
# =====================================================================

sp = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        client_id=my_secrets.CLIENT_ID,
        client_secret=my_secrets.CLIENT_SECRET,
        redirect_uri=my_secrets.REDIRECT_URI,
        scope="playlist-read-private playlist-read-collaborative user-library-read user-read-private",
        open_browser=True
    )
)

# =====================================================================
# DATA MODELS
# =====================================================================

class Track:
    def __init__(
        self,
        track_uri: str,
        track_name: str,
        album_name: str,
        artist_names: list[str],
        release_date: str,
        genres: list[str],
        duration_ms: int,
        popularity: int,
        explicit: bool,
        associated_playlists: list[str]
    ):
        self.track_uri = track_uri
        self.track_name = track_name
        self.album_name = album_name
        self.artist_names = artist_names
        self.release_date = release_date
        self.genres = genres
        self.duration_ms = duration_ms
        self.popularity = popularity
        self.explicit = explicit
        self.associated_playlists = associated_playlists

    def to_dict(self) -> dict:
        return {
            "track_uri": self.track_uri,
            "track_name": self.track_name,
            "album_name": self.album_name,
            "artist_names": self.artist_names,
            "release_date": self.release_date,
            "genres": self.genres,
            "duration_ms": self.duration_ms,
            "popularity": self.popularity,
            "explicit": self.explicit,
            "associated_playlists": self.associated_playlists,
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            track_uri=data["track_uri"],
            track_name=data["track_name"],
            album_name=data["album_name"],
            artist_names=data["artist_names"],
            release_date=data["release_date"],
            genres=data["genres"],
            duration_ms=data["duration_ms"],
            popularity=data["popularity"],
            explicit=data["explicit"],
            associated_playlists=data["associated_playlists"],
        )


class Playlist:
    def __init__(
        self,
        playlist_id: str,
        name: str,
        description: str,
        owner: str,
        contained_tracks: list[str]
    ):
        self.playlist_id = playlist_id
        self.name = name
        self.description = description
        self.owner = owner
        self.contained_tracks = contained_tracks

    def to_dict(self) -> dict:
        return {
            "playlist_id": self.playlist_id,
            "name": self.name,
            "description": self.description,
            "owner": self.owner,
            "contained_tracks": self.contained_tracks,
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            playlist_id=data["playlist_id"],
            name=data["name"],
            description=data["description"],
            owner=data["owner"],
            contained_tracks=data["contained_tracks"],
        )

# =====================================================================
# SAVE AND LOAD
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

# =====================================================================
# SKIP LIST
# =====================================================================

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

    Print(f"Total playlists: {len(playlist_objects)}")
    return playlist_objects, track_counts


def fetch_playlist_tracks(sp, playlist: Playlist, artist_genre_cache: dict):
    raw = safe_spotify_call(sp.playlist_items, playlist.playlist_id)
    items = raw["items"]
    while raw["next"]:
        raw = safe_spotify_call(sp.next, raw)
        items.extend(raw["items"])

    uris = []
    track_map = {}

    total = len(items)
    count = 0

    for item in items:
        count += 1
        progress_bar(playlist.name, count, total)

        t = item["track"]
        if not t:
            continue

        uri = t["uri"]
        uris.append(uri)
        track_map[uri] = t

    print()
    playlist.contained_tracks = uris

    return track_map

# =====================================================================
# BATCH GENRE FETCHING (FIX FOR RATE LIMITS)
# =====================================================================

def fetch_genres_for_artists(sp, artist_ids: list[str], cache: dict):
    """Fetch genres for many artists at once (max 50 per request)."""
    missing = [aid for aid in artist_ids if aid not in cache]

    for i in range(0, len(missing), 50):
        batch = missing[i:i+50]
        result = sp.artists(batch)
        for artist in result["artists"]:
            cache[artist["id"]] = artist.get("genres", [])

# =====================================================================
# UPDATE TRACKS AND PLAYLIST
# =====================================================================

def update_tracks_and_playlist_for_changed(
    sp,
    playlist: Playlist,
    old_playlist: Playlist | None,
    tracks: dict,
    artist_genre_cache: dict
):

    old_uris = set(old_playlist.contained_tracks) if old_playlist else set()

    # Fetch all track items for this playlist
    track_map = fetch_playlist_tracks(sp, playlist, artist_genre_cache)

    # ---------------------------------------------------------
    # NEW: Batch artist genre lookup to avoid rate limits
    # ---------------------------------------------------------

    artist_ids = [
        t["artists"][0]["id"]
        for t in track_map.values()
        if t["artists"]
    ]

    # Deduplicate
    unique_ids = list(set(artist_ids))

    # Populate cache in bulk
    fetch_genres_for_artists(sp, unique_ids, artist_genre_cache)

    # ---------------------------------------------------------

    new_uris = set(playlist.contained_tracks)

    # Update or create track objects
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

        if playlist.playlist_id not in track_obj.associated_playlists:
            track_obj.associated_playlists.append(playlist.playlist_id)

    # Remove old associations
    removed_uris = old_uris - new_uris
    for uri in removed_uris:
        if uri in tracks:
            track_obj = tracks[uri]
            if playlist.playlist_id in track_obj.associated_playlists:
                track_obj.associated_playlists.remove(playlist.playlist_id)

# =====================================================================
# MAIN
# =====================================================================

if __name__ == "__main__":

    Print("Token scope: " +
        sp.auth_manager.get_access_token(as_dict=True).get("scope", "NONE"))

    Print("Checking for saved data.")
    try:
        old_tracks, old_playlists = load_library_from_json()
        Print("Loaded existing library files.")
    except FileNotFoundError:
        old_tracks, old_playlists = {}, {}
        Print("No existing library found. Starting fresh.")

    playlist_list, remote_track_counts = get_all_playlists_and_counts(sp)
    target_names_to_skip = load_skip_list()

    Print("Playlist order:")
    for i, pl in enumerate(playlist_list):
        Print(f"{i}: {pl.name}")


    Print("\nChecking playlists for updates...\n")

    merged_playlists = old_playlists.copy()
    merged_tracks = old_tracks.copy()
    artist_genre_cache = {}

    for pl in playlist_list:
        pl_name = pl.name.lower()

        if pl_name in target_names_to_skip:
            Print(f"Skipping (config): {pl.name}")
            continue

        Print(f"\nChecking: {pl.name}")

        old_p = old_playlists.get(pl.playlist_id)
        remote_count = remote_track_counts.get(pl.playlist_id, 0)
        old_count = len(old_p.contained_tracks) if old_p else -1

        if old_p and remote_count == old_count:
            Print(f"No update needed ({remote_count} tracks)")
            merged_playlists[pl.playlist_id] = old_p
            continue

        Print(f"Updating playlist: {pl.name}")

        # Main update logic (includes batch genre fetch)
        update_tracks_and_playlist_for_changed(
            sp,
            pl,
            old_p,
            merged_tracks,
            artist_genre_cache
        )

        merged_playlists[pl.playlist_id] = pl

    save_library_to_json(merged_tracks, merged_playlists)

    Print("\nDone!")
