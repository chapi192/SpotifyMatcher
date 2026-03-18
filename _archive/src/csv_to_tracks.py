# THIS SCRIPT PULLS DATA FROM DOWNLOADED CSV OF ENTIRE LIBRARY
# AND THEN UPDATES TRACK ATTRIBUTES WITH IT

import csv
import json
import sys
import datetime
from pathlib import Path

# =====================================================================
# PATHS
# =====================================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"

TRACKS_PATH = DATA_DIR / "tracks.json"
CSV_PATH = DATA_DIR / "Complete_Library.csv"   # Exportify CSV file


# =====================================================================
# PROGRESS BAR + PRINT
# =====================================================================

def Print(msg: str):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"{ts} {msg}")
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
# FIELD MAPPINGS
# =====================================================================

AUDIO_FIELDS = {
    "Danceability": "danceability",
    "Energy": "energy",
    "Key": "key",
    "Loudness": "loudness",
    "Mode": "mode",
    "Speechiness": "speechiness",
    "Acousticness": "acousticness",
    "Instrumentalness": "instrumentalness",
    "Liveness": "liveness",
    "Valence": "valence",
    "Tempo": "tempo",
}

GENRE_COLUMN = "Genres"


def parse_genres(csv_value: str):
    """Split CSV list into normalized genre list."""
    if not csv_value:
        return []
    return [g.strip().lower() for g in csv_value.split(",") if g.strip()]


# =====================================================================
# LOAD TRACKS.JSON
# =====================================================================

with TRACKS_PATH.open("r", encoding="utf-8") as f:
    tracks = json.load(f)

Print(f"Loaded {len(tracks)} tracks from JSON.")
Print(f"Reading CSV: {CSV_PATH.name}")


# =====================================================================
# LOAD CSV + PROCESS
# =====================================================================

with CSV_PATH.open("r", encoding="utf-8") as f:
    reader = csv.DictReader(f)

    # Fix BOM
    reader.fieldnames = [h.replace("\ufeff", "") for h in reader.fieldnames]

    rows = list(reader)
    total_rows = len(rows)

    updated_audio = 0
    updated_genres = 0
    missing_in_json = 0

    Print(f"CSV rows detected: {total_rows}")

    # ---------------------------
    # Iterate rows WITH PROGRESS
    # ---------------------------
    for idx, row in enumerate(rows, start=1):

        # update progress bar
        progress_bar("Updating tracks", idx, total_rows)

        uri = row.get("Track URI")
        if not uri:
            continue

        if uri not in tracks:
            missing_in_json += 1
            continue

        track = tracks[uri]

        # ---------------------------
        # Merge Audio Fields
        # ---------------------------
        for csv_col, json_field in AUDIO_FIELDS.items():

            raw = row.get(csv_col)
            if raw is None or raw == "":
                continue

            try:
                if json_field in [
                    "danceability", "energy", "speechiness", "acousticness",
                    "instrumentalness", "liveness", "valence"
                ]:
                    val = float(raw)
                elif json_field in ["loudness", "tempo"]:
                    val = float(raw)
                elif json_field in ["key", "mode"]:
                    val = int(raw)
                else:
                    continue
            except ValueError:
                continue

            if track.get(json_field) is None:
                track[json_field] = val
                updated_audio += 1

        # ---------------------------
        # Merge Genres
        # ---------------------------
        new_genres = parse_genres(row.get(GENRE_COLUMN))
        if new_genres:
            old_genres = track.get("genres", [])
            merged = set(g.lower() for g in old_genres)

            before = len(merged)
            merged.update(new_genres)

            if len(merged) != before:
                track["genres"] = sorted(list(merged))
                updated_genres += 1


# =====================================================================
# SAVE UPDATED JSON
# =====================================================================

with TRACKS_PATH.open("w", encoding="utf-8") as f:
    json.dump(tracks, f, indent=4)


# =====================================================================
# SUMMARY
# =====================================================================

Print("")
Print(f"CSV rows processed:        {total_rows}")
Print(f"Tracks missing in JSON:    {missing_in_json}")
Print(f"Audio fields updated:      {updated_audio}")
Print(f"Genre lists updated:       {updated_genres}")
Print("Done merging Exportify data!")
