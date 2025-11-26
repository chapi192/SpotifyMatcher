#THIS SCRIPT 

import spotipy
from spotipy.oauth2 import SpotifyOAuth
import json

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
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri="http://127.0.0.1:8888/callback",
        scope="playlist-read-private playlist-read-collaborative user-library-read user-read-private",
        open_browser=True
    )
)

class Track:
    def __init__(
        self,
        track_uri,
        track_name,
        album_name,
        artist_names,
        release_date,
        genres,
        duration_ms,
        popularity,
        explicit,
        associated_playlists
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

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


class Playlist:
    def __init__(self, playlist_id, name, description, owner, contained_tracks):
        self.playlist_id = playlist_id
        self.name = name
        self.description = description
        self.owner = owner
        self.contained_tracks = contained_tracks

    @classmethod
    def from_dict(cls, d):
        return cls(**d)

def load_library():
    with open("tracks.json", "r", encoding="utf-8") as f:
        raw_tracks = json.load(f)

    with open("playlists.json", "r", encoding="utf-8") as f:
        raw_playlists = json.load(f)

    tracks = {uri: Track.from_dict(t) for uri, t in raw_tracks.items()}
    playlists = {pid: Playlist.from_dict(p) for pid, p in raw_playlists.items()}

    Print(f"Loaded {len(tracks)} tracks and {len(playlists)} playlists.")
    return tracks, playlists

def build_playlist_stats(tracks, playlists):
    stats = {}

    for pid, pl in playlists.items():
        genre_counts = {}
        artist_counts = {}
        popularity_sum = 0
        count = len(pl.contained_tracks)

        for uri in pl.contained_tracks:
            t = tracks.get(uri)
            if not t:
                continue

            # genres
            for g in t.genres:
                genre_counts[g] = genre_counts.get(g, 0) + 1

            # artists
            for a in t.artist_names:
                artist_counts[a] = artist_counts.get(a, 0) + 1

            # popularity
            popularity_sum += t.popularity

        stats[pid] = {
            "name": pl.name,
            "track_count": count,
            "genre_counts": genre_counts,
            "artist_counts": artist_counts,
            "unique_genres": len(genre_counts),
            "unique_artists": len(artist_counts),
            "avg_popularity": popularity_sum / count if count else 0
        }

    return stats

def save_playlist_stats(stats):
    with open("playlist_stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=4)

tracks, playlists = load_library()

playlist_stats = build_playlist_stats(tracks, playlists)

save_playlist_stats(playlist_stats)

Print("Playlist stats built and saved.")