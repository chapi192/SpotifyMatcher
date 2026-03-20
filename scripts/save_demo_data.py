import json
import spotipy
from spotipy.oauth2 import SpotifyOAuth

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from web.services.fetch_data import fetch_single_playlist


# ----------------------------------------
# CONFIG
# ----------------------------------------

CLIENT_ID = "YOUR_CLIENT_ID"
CLIENT_SECRET = "YOUR_CLIENT_SECRET"
REDIRECT_URI = "http://127.0.0.1:8000/callback"  # match your app

PLAYLIST_NAMES = [
    "Big Band / Swing",
    "Rockin 60s",
    "Birth Of Rock",
    "Escape the Machine",
    "I've Got To Drive Fast",
    "60s Pop",
    "Genuinely sad",
    "Electroswing",
    "Indie/Alt",
    "Country",
    "Honky Tonk",
    "Opera",
    "Bluegrass",
]


# ----------------------------------------
# AUTH (USER LOGIN)
# ----------------------------------------

def get_spotify():

    return spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            redirect_uri=REDIRECT_URI,
            scope="playlist-read-private playlist-read-collaborative"
        )
    )


# ----------------------------------------
# FIND PLAYLIST IDS BY NAME
# ----------------------------------------

def get_playlist_ids(sp):

    results = sp.current_user_playlists(limit=50)

    found = {}
    missing = set(PLAYLIST_NAMES)

    while results:

        for p in results["items"]:
            name = p["name"]

            if name in PLAYLIST_NAMES:
                found[name] = p["id"]
                missing.discard(name)

        if not results["next"]:
            break

        results = sp.next(results)

    if missing:
        print("\n⚠️ Missing playlists:")
        for m in missing:
            print(f" - {m}")

    return found


# ----------------------------------------
# BUILD DATASET
# ----------------------------------------

def build_dataset():

    sp = get_spotify()

    playlist_map = get_playlist_ids(sp)

    dataset = {}
    artist_cache = {}

    for name, pid in playlist_map.items():

        print(f"Fetching: {name}")

        playlist = fetch_single_playlist(
            sp,
            pid,
            artist_cache=artist_cache
        )

        if not playlist:
            continue

        dataset[pid] = playlist

    return dataset


# ----------------------------------------
# SAVE
# ----------------------------------------

def save_json(data):

    with open("static/demoData.json", "w") as f:
        json.dump(data, f, indent=2)

    print("\n✅ Saved static/demoData.json")


# ----------------------------------------
# RUN
# ----------------------------------------

if __name__ == "__main__":

    data = build_dataset()
    save_json(data)