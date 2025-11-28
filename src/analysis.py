# TAKES RAW JSON FILES AND OUTPUTS PROCESSED PLAYLIST STATS
# INCLUDING AUDIO FEATURE DISTRIBUTIONS AND EMBEDDING VECTORS.

import json
import numpy as np
import datetime
import sys
from pathlib import Path
from models import Track, Playlist

# =====================================================================
# DEBUG + PROGRESS BAR
# =====================================================================

debug = True

def Print(msg: str):
    if debug:
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        msg = msg.replace("→", "->")
        print(f"{ts} {msg}")
        sys.stdout.flush()

def progress_bar(prefix, index, total, bar_length=25):
    if total <= 0:
        return
    frac = index / total
    filled = int(bar_length * frac)
    bar = "#" * filled + "-" * (bar_length - filled)
    print(f"\r{prefix[:22]:22} [{bar}] {index}/{total}", end="", flush=True)
    if index == total:
        print()

# =====================================================================
# PATHS
# =====================================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"
PROC_DIR = BASE_DIR / "data" / "processed"
PROC_DIR.mkdir(parents=True, exist_ok=True)

TRACKS_PATH = DATA_DIR / "tracks.json"
PLAYLISTS_PATH = DATA_DIR / "playlists.json"
OUTPUT_PATH = PROC_DIR / "playlist_stats.json"

SKIP_FILE = BASE_DIR / "config" / "skip_playlists.txt"

# =====================================================================
# LOAD SKIP LIST
# =====================================================================

def load_skip_list():
    if not SKIP_FILE.exists():
        return set()
    with SKIP_FILE.open("r", encoding="utf-8") as f:
        return {line.strip().lower() for line in f if line.strip()}

# =====================================================================
# LOAD LIBRARY JSON
# =====================================================================

def load_library():
    Print("Loading library...")

    with TRACKS_PATH.open("r", encoding="utf-8") as f:
        raw_tracks = json.load(f)

    with PLAYLISTS_PATH.open("r", encoding="utf-8") as f:
        raw_playlists = json.load(f)

    tracks = {uri: Track.from_dict(t) for uri, t in raw_tracks.items()}
    playlists = {pid: Playlist.from_dict(p) for pid, p in raw_playlists.items()}

    Print(f"Loaded {len(tracks)} tracks, {len(playlists)} playlists.")
    return tracks, playlists

# =====================================================================
# SUMMARY HELPERS
# =====================================================================

def summarize(values):
    arr = np.array(values, dtype=float)
    return {
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
        "stdev": float(np.std(arr)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "p25": float(np.percentile(arr, 25)),
        "p75": float(np.percentile(arr, 75)),
    }

# =====================================================================
# BUILD STATS
# =====================================================================

def build_playlist_stats(tracks, playlists):
    Print("Building playlist stats...")

    stats = {}
    playlist_items = list(playlists.items())
    total = len(playlist_items)

    for idx, (pid, pl) in enumerate(playlist_items, start=1):
        # Update progress bar
        progress_bar("Playlists", idx, total)

        track_objs = [tracks.get(uri) for uri in pl.contained_tracks]
        track_objs = [t for t in track_objs if t is not None]

        if not track_objs:
            continue

        # Counters
        genre_counts = {}
        artist_counts = {}

        # Audio feature lists
        feats = {
            "danceability": [],
            "energy": [],
            "valence": [],
            "acousticness": [],
            "instrumentalness": [],
            "speechiness": [],
            "liveness": [],
            "loudness": [],
            "tempo": [],
        }

        keys = []
        modes = []

        for t in track_objs:
            for g in t.genres:
                genre_counts[g] = genre_counts.get(g, 0) + 1

            for a in t.artist_names:
                artist_counts[a] = artist_counts.get(a, 0) + 1

            if t.danceability is not None: feats["danceability"].append(t.danceability)
            if t.energy is not None: feats["energy"].append(t.energy)
            if t.valence is not None: feats["valence"].append(t.valence)
            if t.acousticness is not None: feats["acousticness"].append(t.acousticness)
            if t.instrumentalness is not None: feats["instrumentalness"].append(t.instrumentalness)
            if t.speechiness is not None: feats["speechiness"].append(t.speechiness)
            if t.liveness is not None: feats["liveness"].append(t.liveness)
            if t.loudness is not None: feats["loudness"].append(t.loudness)
            if t.tempo is not None: feats["tempo"].append(t.tempo)
            if t.key is not None: keys.append(t.key)
            if t.mode is not None: modes.append(t.mode)

        audio_stats = {}
        for k, vals in feats.items():
            if vals:
                audio_stats[k] = summarize(vals)

        # key distribution
        key_counts = {str(i): 0 for i in range(12)}
        for k in keys:
            key_counts[str(k)] += 1

        mode_counts = {"0": 0, "1": 0}
        for m in modes:
            mode_counts[str(m)] += 1

        total_modes = mode_counts["0"] + mode_counts["1"]
        percent_major = (mode_counts["1"] / total_modes) if total_modes else 0.5

        # Embedding vector
        def med_or_zero(name):
            return audio_stats[name]["median"] if name in audio_stats else 0.0

        embedding_vector = [
            med_or_zero("danceability"),
            med_or_zero("energy"),
            med_or_zero("valence"),
            med_or_zero("acousticness"),
            med_or_zero("instrumentalness"),
            med_or_zero("speechiness"),
            med_or_zero("liveness"),
            abs(med_or_zero("loudness")),      # invert loudness
            med_or_zero("tempo") / 200.0,      # normalize tempo
        ]

        stats[pid] = {
            "playlist_id": pid,
            "name": pl.name,
            "track_count": len(track_objs),
            "unique_genres": len(genre_counts),
            "unique_artists": len(artist_counts),
            "genre_counts": genre_counts,
            "artist_counts": artist_counts,
            "audio_stats": audio_stats,
            "key_distribution": key_counts,
            "most_common_key": max(key_counts, key=lambda k: key_counts[k]),
            "mode_distribution": mode_counts,
            "percent_major": percent_major,
            "embedding_vector": embedding_vector,
        }

    return stats

# =====================================================================
# SAVE
# =====================================================================

def save_stats(stats):
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(stats, f, indent=4)
    Print(f"Saved playlist stats to {OUTPUT_PATH}")

# =====================================================================
# MAIN
# =====================================================================

if __name__ == "__main__":

    tracks, playlists = load_library()

    skip_names = load_skip_list()
    Print(f"Skipping {len(skip_names)} playlists from stats...")

    playlists = {
        pid: pl for pid, pl in playlists.items()
        if pl.name.lower() not in skip_names
    }

    Print(f"Remaining playlists: {len(playlists)}")

    stats = build_playlist_stats(tracks, playlists)
    save_stats(stats)

    Print("Done building playlist stats.")
