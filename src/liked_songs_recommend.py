# PRODUCES LIKED SONGS RECCOMENDATOR CSV FOR WHERE TO PUT STUFF IN YOUR LIBRARY

import csv
import json
import numpy as np
from pathlib import Path
import subprocess
import platform

# -----------------------------------
# CONFIG
# -----------------------------------

PRECISION = 5

WEIGHT_EMBED = 0.50
WEIGHT_GENRE = 0.20
WEIGHT_MOOD  = 0.20
WEIGHT_TEMPO = 0.10

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "data" / "raw"
PROC = BASE / "data" / "processed"
CONFIG = BASE / "config"

LIKED_SONGS_CSV = RAW / "Liked_Songs.csv"
TRACKS_JSON = RAW / "tracks.json"
STATS_JSON = PROC / "playlist_stats.json"
SKIP_FILE = CONFIG / "skip_playlists.txt"

OUTPUT_CSV = BASE / "data" / "results" / "recommend_liked_songs.csv"
OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

# -------------------------------------------------------
# LOADERS
# -------------------------------------------------------

def load_tracks():
    with TRACKS_JSON.open("r", encoding="utf-8") as f:
        return json.load(f)

def load_stats():
    with STATS_JSON.open("r", encoding="utf-8") as f:
        return json.load(f)

def load_skip_list():
    if not SKIP_FILE.exists():
        return set()
    with SKIP_FILE.open("r", encoding="utf-8") as f:
        return {line.strip().lower() for line in f if line.strip()}

def load_liked_csv():
    with LIKED_SONGS_CSV.open("r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

# -------------------------------------------------------
# HELPERS
# -------------------------------------------------------

def safe_diff(a, b):
    if a is None or b is None:
        return float("inf")
    return abs(a - b)

# -------------------------------------------------------
# SCORING
# -------------------------------------------------------

def score_song_against_playlist(song, pl):

    # Audio feature vector (9 values total)
    sv = [
        song.get("danceability"),
        song.get("energy"),
        song.get("valence"),
        song.get("acousticness"),
        song.get("instrumentalness"),
        song.get("speechiness"),
        song.get("liveness"),
        song.get("loudness"),
        song.get("tempo"),
    ]

    pv = pl.get("embedding_vector")

    # Embedding distance
    if any(v is None for v in sv) or pv is None:
        embed = float("inf")
    else:
        sv_norm = sv.copy()
        pv_norm = pv.copy()

        # normalize loudness/tempo
        sv_norm[7] /= 20
        sv_norm[8] /= 200
        pv_norm[7] /= 20
        pv_norm[8] /= 200

        embed = float(np.linalg.norm(np.array(sv_norm) - np.array(pv_norm)))

    # Genre match
    s_genres = set(song.get("genres", []))
    p_genres = {g for g, c in pl.get("genre_counts", {}).items() if c >= 2}

    if not s_genres:
        genre_score = 0
    else:
        genre_score = len(s_genres.intersection(p_genres)) / len(s_genres)

    # Mood
    mood = safe_diff(song.get("valence"), pl["audio_stats"]["valence"]["median"])

    # Tempo
    tempo = safe_diff(song.get("tempo"), pl["audio_stats"]["tempo"]["median"]) / 200

    # Final weighted score
    total = (
        embed * WEIGHT_EMBED +
        (1 - genre_score) * WEIGHT_GENRE +
        mood * WEIGHT_MOOD +
        tempo * WEIGHT_TEMPO
    )

    return {
        "total": total,
        "embed": embed,
        "genre": genre_score,
        "mood": mood,
        "tempo": tempo,
    }

# -------------------------------------------------------
# MAIN
# -------------------------------------------------------

def process():
    tracks = load_tracks()
    stats = load_stats()
    liked = load_liked_csv()
    skip = load_skip_list()

    playlist_by_id = stats

    # Only include non-skipped playlists
    active_playlists = {
        pid: pl
        for pid, pl in playlist_by_id.items()
        if pl["name"].lower() not in skip
    }

    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        writer.writerow([
            "Track Name",
            "Overall",
            "Embed",
            "Genre",
            "Mood",
            "Tempo",
        ])

        for row in liked:
            track_name = row["Track Name"]
            uri = row["Track URI"]

            song = tracks.get(uri)
            if not song:
                continue

            # Score comparisons
            results = {
                pl["name"]: score_song_against_playlist(song, pl)
                for pl in active_playlists.values()
            }

            sorted_overall = sorted(results.items(), key=lambda x: x[1]["total"])[:PRECISION]
            sorted_embed   = sorted(results.items(), key=lambda x: x[1]["embed"])[:PRECISION]
            sorted_genre   = sorted(results.items(), key=lambda x: x[1]["genre"], reverse=True)[:PRECISION]
            sorted_mood    = sorted(results.items(), key=lambda x: x[1]["mood"])[:PRECISION]
            sorted_tempo   = sorted(results.items(), key=lambda x: x[1]["tempo"])[:PRECISION]

            # Write rows
            for i in range(PRECISION):
                writer.writerow([
                    track_name if i == 0 else "",
                    sorted_overall[i][0],
                    sorted_embed[i][0],
                    sorted_genre[i][0],
                    sorted_mood[i][0],
                    sorted_tempo[i][0],
                ])

            writer.writerow([])

    print("Done! Opening:", OUTPUT_CSV)

    if platform.system() == "Windows":
        subprocess.Popen(["start", str(OUTPUT_CSV)], shell=True)
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", str(OUTPUT_CSV)])
    else:
        subprocess.Popen(["xdg-open", str(OUTPUT_CSV)])

if __name__ == "__main__":
    process()
