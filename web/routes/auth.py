from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse
import spotipy
import hmac
import secrets

from web.spotify_auth import build_oauth, get_user_id, get_spotify_client
from web.state import PLAYLIST_DATA_CACHE, PLAYLIST_CACHE

router = APIRouter()

@router.get("/login")
def login(request: Request):
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    oauth = build_oauth(request, state=state)
    return RedirectResponse(oauth.get_authorize_url())

@router.get("/logout")
def logout(request: Request):
    sp = get_spotify_client(request)
    if sp:
        user_id = get_user_id(request)
        PLAYLIST_DATA_CACHE.pop(user_id, None)
        PLAYLIST_CACHE.pop(user_id, None)

    request.session.clear()
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("session")
    return response

@router.get("/callback")
def callback(request: Request):
    error = request.query_params.get("error")
    if error:
        return RedirectResponse(url="/")

    code = request.query_params.get("code")
    if not code:
        return RedirectResponse(url="/")

    expected_state = request.session.pop("oauth_state", None)
    returned_state = request.query_params.get("state")
    if not expected_state or not returned_state or not hmac.compare_digest(expected_state, returned_state):
        return JSONResponse({"error": "Invalid OAuth state"}, status_code=400)

    oauth = build_oauth(request, state=expected_state)

    token_info = oauth.get_access_token(code, check_cache=False)
    request.session["token_info"] = token_info

    sp = spotipy.Spotify(auth_manager=oauth)
    user_id = sp.current_user()["id"]
    request.session["user_id"] = user_id

    return RedirectResponse("/dashboard")
