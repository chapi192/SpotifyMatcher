# THIS SCRIPT MAKES A PLAYLIST ON SPOTIFY CALLED "COMPLETE LIBRARY" FROM ALL TRACKS ON PREVIOUS STEPS. MUST BE DOWNLOADED FROM EXPORTIFY.COM FOR CSV_TO_TRACKS.PY

import json
import time
import re
from pathlib import Path
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import my_secrets

PLAYLIST_NAME = "Complete Library"

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"
TRACKS_PATH = DATA_DIR / "tracks.json"

# -----------------------------------------------------
# Spotify auth
# -----------------------------------------------------
sp = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        client_id=my_secrets.CLIENT_ID,
        client_secret=my_secrets.CLIENT_SECRET,
        redirect_uri=my_secrets.REDIRECT_URI,
        scope="playlist-modify-public playlist-modify-private playlist-read-private",
        open_browser=True
    )
)

# -----------------------------------------------------
# Load track URIs
# -----------------------------------------------------
with TRACKS_PATH.open("r", encoding="utf-8") as f:
    raw_tracks = json.load(f)

all_uris = list(raw_tracks.keys())
print(f"Loaded {len(all_uris)} total tracks from tracks.json.")

# -----------------------------------------------------
# URI validation function
# -----------------------------------------------------
VALID_URI_REGEX = re.compile(r"^spotify:track:[A-Za-z0-9]{22}$")

def is_valid_track_uri(uri):
    return isinstance(uri, str) and VALID_URI_REGEX.match(uri) is not None

# -----------------------------------------------------
# Find or create playlist
# -----------------------------------------------------
def get_or_create_playlist(name):
    results = sp.current_user_playlists(limit=50)
    items = results["items"]

    while results["next"]:
        results = sp.next(results)
        items.extend(results["items"])

    for pl in items:
        if pl["name"].lower() == name.lower():
            print(f"Playlist '{name}' found. ID = {pl['id']}")
            return pl["id"]

    print(f"Creating playlist '{name}'...")
    user_id = sp.current_user()["id"]
    created = sp.user_playlist_create(
        user=user_id,
        name=name,
        public=False,
        description="Auto-generated library of all tracks"
    )
    print(f"Playlist created. ID = {created['id']}")
    return created["id"]

playlist_id = get_or_create_playlist(PLAYLIST_NAME)

# -----------------------------------------------------
# Fetch existing tracks so we don't re-add
# -----------------------------------------------------
print("Fetching existing tracks in playlist...")

existing = set()
results = sp.playlist_items(playlist_id, limit=100)
items = results["items"]

while results["next"]:
    results = sp.next(results)
    items.extend(results["items"])

for it in items:
    t = it.get("track")
    if t and t.get("uri"):
        existing.add(t["uri"])

print(f"Playlist already has {len(existing)} tracks.")

# -----------------------------------------------------
# Determine which tracks to add
# -----------------------------------------------------
invalid_uris = []
to_add = []

for uri in all_uris:
    if not is_valid_track_uri(uri):
        invalid_uris.append(uri)
        continue
    if uri not in existing:
        to_add.append(uri)

print(f"Valid URIs to add: {len(to_add)}")
print(f"Invalid/skipped URIs: {len(invalid_uris)}")

# -----------------------------------------------------
# Add tracks in batches — skipping only invalid ones
# -----------------------------------------------------
added = 0

for i in range(0, len(to_add), 100):
    batch = to_add[i:i+100]
    print(f"Adding batch {i//100+1} ({len(batch)} tracks)...")

    try:
        sp.playlist_add_items(playlist_id, batch)
        added += len(batch)
    except Exception as e:
        print(f"Batch failed with error: {e}")
        print("Attempting to add tracks individually...")

        # fallback: add one-by-one, skipping failures
        for uri in batch:
            try:
                sp.playlist_add_items(playlist_id, [uri])
                added += 1
            except Exception as e2:
                print(f"  Skipping invalid URI: {uri}  ({e2})")
                invalid_uris.append(uri)

    time.sleep(0.2)  # avoid hammering the API

# -----------------------------------------------------
# Summary
# -----------------------------------------------------
print("\n================ SUMMARY ================")
print(f"Tracks loaded:         {len(all_uris)}")
print(f"Already in playlist:   {len(existing)}")
print(f"Added successfully:    {added}")
print(f"Skipped (invalid):     {len(invalid_uris)}")

if invalid_uris:
    print("\nInvalid URIs:")
    for u in invalid_uris:
        print(" -", u)

print("Done!")
