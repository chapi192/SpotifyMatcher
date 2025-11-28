# TAKES RAW JSON FILES AND OUTPUTS TO A PROCESSED JSON FOR WORKING OFF OF

import json
from pathlib import Path
from models import Track, Playlist

debug = True
def Print(msg: str):
    if debug:
        print(msg)

# -------------------------------------------------------
# Paths
# -------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent  # Exportify/
DATA_DIR = BASE_DIR / "data" / "raw"

TRACKS_PATH = DATA_DIR / "tracks.json"
PLAYLISTS_PATH = DATA_DIR / "playlists.json"
OUTPUT_PATH = BASE_DIR / "data" / "processed" / "playlist_stats.json"
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# -------------------------------------------------------
# Load Library (offline)
# -------------------------------------------------------

def load_library():
    Print("Loading library...")

    with TRACKS_PATH.open("r", encoding="utf-8") as f:
        raw_tracks = json.load(f)

    with PLAYLISTS_PATH.open("r", encoding="utf-8") as f:
        raw_playlists = json.load(f)

    tracks = {uri: Track.from_dict(t) for uri, t in raw_tracks.items()}
    playlists = {pid: Playlist.from_dict(p) for pid, p in raw_playlists.items()}

    Print(f"Loaded {len(tracks)} tracks and {len(playlists)} playlists.")
    return tracks, playlists

# -------------------------------------------------------
# Build Stats
# -------------------------------------------------------

def build_playlist_stats(tracks, playlists):
    stats = {}

    for pid, pl in playlists.items():
        genre_counts = {}
        artist_counts = {}
        popularity_sum = 0
        track_count = len(pl.contained_tracks)

        for uri in pl.contained_tracks:
            t = tracks.get(uri)
            if not t:
                continue

            # Genres
            for g in t.genres:
                genre_counts[g] = genre_counts.get(g, 0) + 1

            # Artists
            for a in t.artist_names:
                artist_counts[a] = artist_counts.get(a, 0) + 1

            # Popularity
            popularity_sum += t.popularity

        stats[pid] = {
            "playlist_id": pid,
            "name": pl.name,
            "track_count": track_count,
            "unique_genres": len(genre_counts),
            "unique_artists": len(artist_counts),
            "avg_popularity": popularity_sum / track_count if track_count else 0,
            "genre_counts": genre_counts,
            "artist_counts": artist_counts,
        }

    return stats

# -------------------------------------------------------
# Save Results
# -------------------------------------------------------

def save_playlist_stats(stats):
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(stats, f, indent=4)
    Print(f"Saved stats → {OUTPUT_PATH}")

# -------------------------------------------------------
# Main
# -------------------------------------------------------

if __name__ == "__main__":
    tracks, playlists = load_library()
    stats = build_playlist_stats(tracks, playlists)
    save_playlist_stats(stats)
    Print("Done building playlist stats.")
