#THIS SCRIPT PULLS DATA DIRECTLY FROM SPOTIFY USING YOUR ACCOUNT'S CREDENTIALS AND SAVES IT LOCALLY AS JSON FILES.
#NO ANALYSIS PERFORMED HERE.

import spotipy
import my_secrets
from spotipy.oauth2 import SpotifyOAuth
import json

from pathlib import Path

# Base directory for project files
BASE_DIR = Path(__file__).resolve().parent.parent  # Exportify/
DATA_DIR = BASE_DIR / "data" / "raw"

# Ensure the data/raw folder exists
DATA_DIR.mkdir(parents=True, exist_ok=True)


debug = True
def Print(msg: str):
    if debug:
        print(msg)

def progress_bar(prefix, index, total, bar_length=20):
    filled = int(bar_length * index / total)
    bar = "#" * filled + "-" * (bar_length - filled)
    print(f"\r{prefix}: [{bar}] {index}/{total}", end="")

sp = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        client_id = my_secrets.CLIENT_ID,
        client_secret = my_secrets.CLIENT_SECRET,
        redirect_uri = my_secrets.REDIRECT_URI,
        scope="playlist-read-private playlist-read-collaborative user-library-read user-read-private",
        open_browser=True
    )
)

Print("Token scope: " + sp.auth_manager.get_access_token(as_dict=True).get("scope", "NONE"))

def save_library_to_json(tracks: dict, playlists: dict):
    tracks_path = DATA_DIR / "tracks.json"
    playlists_path = DATA_DIR / "playlists.json"

    with tracks_path.open("w", encoding="utf-8") as f:
        json.dump(
            {uri: t.to_dict() for uri, t in tracks.items()},
            f,
            indent=4
        )

    with playlists_path.open("w", encoding="utf-8") as f:
        json.dump(
            {pid: p.to_dict() for pid, p in playlists.items()},
            f,
            indent=4
        )

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

class Track:
    def __init__(
        self,
        track_uri: str,
        track_name: str,
        album_name: str,
        artist_names: list[str],
        release_date: str,
        genres: list[str],   # Can be obtained from ARTISTS, still available
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


    # ------- JSON Support ------- #

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
            associated_playlists=data["associated_playlists"]
        )

class Playlist:
    def __init__(
        self,
        playlist_id: str,
        name: str,
        description: str,
        owner: str,
        contained_tracks: list[str]  # URIs
    ):
        self.playlist_id = playlist_id
        self.name = name
        self.description = description
        self.owner = owner
        self.contained_tracks = contained_tracks

    # ------- JSON Support ------- #

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

def get_all_playlists_into_playlist_object(sp):
    Print("Fetching playlists...")

    playlists = sp.current_user_playlists()
    items = playlists["items"]

    names = []

    for pl in playlists["items"]:
        names.append(pl["name"])

    while playlists["next"]:
        playlists = sp.next(playlists)
        items.extend(playlists["items"])
        for pl in playlists["items"]:
            names.append(pl["name"])

    Print(", ".join(names))
    Print(f"Total playlists: {len(names)}")

    playlist_objects = [
        Playlist(
            playlist_id=pl["id"],
            name=pl["name"],
            description=pl.get("description", ""),
            owner=pl["owner"]["display_name"],
            contained_tracks=[]
        )
        for pl in items
    ]

    return playlist_objects

def build_track_object(t, artist_genres):
    return Track(
        track_uri=t["uri"],
        track_name=t["name"],
        album_name=t["album"]["name"],
        artist_names=[a["name"] for a in t["artists"]],
        release_date=t["album"]["release_date"],
        genres=artist_genres,
        duration_ms=t["duration_ms"],
        popularity=t["popularity"],
        explicit=t["explicit"],
        associated_playlists=[]
    )

def get_tracks_for_selected_playlists(sp, playlist_list, target_names):

    MONTHS = [
    "january","february","march","april","may","june",
    "july","august","september","october","november","december",
    "jan","feb","mar","apr","jun","jul","aug","sep","sept","oct","nov","dec"
    ]

    Print("Fetching tracks...")

    tracks = {}
    track_names = []
    artist_genre_cache = {}  # artist_id -> genres

    for pl in playlist_list:
        pl_name = pl.name.lower()

        # Skip playlists explicitly excluded by name
        if pl_name in target_names:
            Print(f"Skipping playlist (excluded): {pl.name}")
            continue

        # Skip playlists containing any month name
        if any(m in pl_name for m in MONTHS):
            continue

        raw_tracks = sp.playlist_items(pl.playlist_id)
        items = raw_tracks["items"]

        while raw_tracks["next"]:
            raw_tracks = sp.next(raw_tracks)
            items.extend(raw_tracks["items"])

        total_tracks = len(items)
        count = 0

        for item in items:
            count += 1
            progress_bar(pl.name, count, total_tracks)

            t = item["track"]
            if not t:
                continue

            uri = t["uri"]

            # --- primary artist ID ---
            artist_id = (
                t["artists"][0]["id"]
                if t["artists"] and t["artists"][0]["id"]
                else None
            )

            # --- genres from artist ---
            if not artist_id:
                genres = []
            else:
                if artist_id in artist_genre_cache:
                    genres = artist_genre_cache[artist_id]
                else:
                    artist_data = sp.artist(artist_id)
                    genres = artist_data.get("genres", [])
                    artist_genre_cache[artist_id] = genres

            # --- build new track ---
            if uri not in tracks:
                track_obj = build_track_object(t, genres)
                tracks[uri] = track_obj
                track_names.append(track_obj.track_name)

            tracks[uri].associated_playlists.append(pl.playlist_id)

        print()  # newline after each playlist's progress bar

        pl.contained_tracks = [
            item["track"]["uri"] for item in items if item["track"]
        ]

    Print(f"Total tracks: {len(track_names)}")

    return tracks

# Pull playlists fresh
playlist_list = get_all_playlists_into_playlist_object(sp)

# Choose which playlists to scan
target_names_to_SKIP = {}

# Pull tracks fresh
tracks = get_tracks_for_selected_playlists(sp, playlist_list, target_names_to_SKIP)

# Save everything freshly to JSON
save_library_to_json(tracks, {p.playlist_id: p for p in playlist_list})

Print("Done!")
