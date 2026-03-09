import os
import time
from spotipy.oauth2 import SpotifyOAuth
import spotipy
from fastapi import Request

SCOPES = [
    "user-read-private",
    "user-read-email",

    "playlist-read-private",
    "playlist-read-collaborative",

    "user-library-read",
    "playlist-modify-private",
    "playlist-modify-public",
    "user-library-modify",
]


def build_oauth():
    return SpotifyOAuth(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
        scope=" ".join(SCOPES),
        show_dialog=True,
        cache_handler=None
    )

def is_token_expired(token_info: dict) -> bool:
    return token_info.get("expires_at", 0) - int(time.time()) < 60

def refresh_if_needed(oauth: SpotifyOAuth, token_info: dict) -> dict:
    if not token_info:
        return None

    if is_token_expired(token_info):
        return oauth.refresh_access_token(token_info["refresh_token"])

    return token_info

def get_spotify_client(request: Request):
    token_info = request.session.get("token_info")

    if not token_info:
        print("NO TOKEN IN SESSION")
        return None

    oauth = build_oauth()
    token_info = refresh_if_needed(oauth, token_info)

    if not token_info:
        print("REFRESH FAILED")
        return None

    request.session["token_info"] = token_info
    oauth.token_info = token_info
    
    return spotipy.Spotify(auth_manager=oauth)

def get_user_id(request: Request):
    user_id = request.session.get("user_id")

    if user_id:
        return user_id

    sp = get_spotify_client(request)
    if not sp:
        return None

    user_id = sp.current_user()["id"]
    request.session["user_id"] = user_id
    return user_id