# csv_to_tracks.py
# Merge audio features & genres from Exportify CSV into tracks.json.
# - Never overwrites existing values unless they were None.
# - Merges genres as a union.
# - Fixes UTF-8 BOM on first column.
# - Track URI is the lookup key.

import csv
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"

TRACKS_PATH = DATA_DIR / "tracks.json"
CSV_PATH = DATA_DIR / "Complete_Library.csv"   # Your Exportify file

# CSV column → JSON field mapping
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


# --------------------------------------------------------
# Load tracks.json
# --------------------------------------------------------
with TRACKS_PATH.open("r", encoding="utf-8") as f:
    tracks = json.load(f)

print(f"Loaded {len(tracks)} tracks from JSON.")
print(f"Reading CSV: {CSV_PATH.name}")


# --------------------------------------------------------
# Load CSV and fix BOM in headers
# --------------------------------------------------------
with CSV_PATH.open("r", encoding="utf-8") as f:
    reader = csv.DictReader(f)

    # Strip UTF-8 BOM (appears as \ufeff)
    reader.fieldnames = [h.replace("\ufeff", "") for h in reader.fieldnames]

    updated_audio = 0
    updated_genres = 0
    csv_rows = 0
    missing_in_json = 0

    # ---------------------------
    # Iterate CSV rows
    # ---------------------------
    for row in reader:
        csv_rows += 1

        uri = row.get("Track URI")
        if not uri:
            continue

        # Track not in our library
        if uri not in tracks:
            missing_in_json += 1
            continue

        track = tracks[uri]

        # ---------------------------
        # Merge audio features
        # ---------------------------
        for csv_col, json_field in AUDIO_FIELDS.items():
            raw = row.get(csv_col)

            if raw is None or raw == "":
                continue

            # Type-cast
            try:
                if json_field in ["danceability", "energy", "speechiness",
                                  "acousticness", "instrumentalness",
                                  "liveness", "valence"]:
                    val = float(raw)
                elif json_field in ["loudness", "tempo"]:
                    val = float(raw)
                elif json_field in ["key", "mode"]:
                    val = int(raw)
                else:
                    continue
            except ValueError:
                continue

            # Only update fields that were None in JSON
            if track.get(json_field) is None:
                track[json_field] = val
                updated_audio += 1

        # ---------------------------
        # Merge genres (union)
        # ---------------------------
        new_genres = parse_genres(row.get(GENRE_COLUMN))
        if new_genres:
            old_genres = track.get("genres", [])
            old_genres_norm = [g.lower() for g in old_genres]

            merged = set(old_genres_norm)
            before = len(merged)

            for g in new_genres:
                merged.add(g)

            if len(merged) != before:
                track["genres"] = sorted(list(merged))
                updated_genres += 1


# --------------------------------------------------------
# Save updated JSON
# --------------------------------------------------------
with TRACKS_PATH.open("w", encoding="utf-8") as f:
    json.dump(tracks, f, indent=4)

# --------------------------------------------------------
# Summary
# --------------------------------------------------------
print("========================================")
print(f"CSV rows processed:        {csv_rows}")
print(f"Tracks missing in JSON:    {missing_in_json}")
print(f"Audio fields updated:      {updated_audio}")
print(f"Genre lists updated:       {updated_genres}")
print("Done merging Exportify data!")
