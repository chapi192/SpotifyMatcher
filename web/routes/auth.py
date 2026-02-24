from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse
import spotipy

from web.spotify_auth import build_oauth, get_user_id, refresh_if_needed, get_spotify_client
from web.state import USER_BUILD_STATE, PLAYLIST_DATA_CACHE, PLAYLIST_CACHE, BUILD_STATE

router = APIRouter()

@router.get("/login")
def login():
    oauth = build_oauth()
    return RedirectResponse(oauth.get_authorize_url())


@router.get("/logout")
def logout(request: Request):

    sp = get_spotify_client(request)
    if sp:
        from web.spotify_auth import get_user_id
        user_id = get_user_id(request)
        USER_BUILD_STATE.pop(user_id, None)
        PLAYLIST_DATA_CACHE.pop(user_id, None)
        PLAYLIST_CACHE.pop(user_id, None)
        BUILD_STATE.pop(user_id, None)
        
    request.session.clear()
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("session")
    return response


def get_spotify_client(request: Request):
    token_info = request.session.get("token_info")

    # print("TOKEN BEFORE REFRESH:", token_info)

    if not token_info:
        print("NO TOKEN IN SESSION")
        return None

    oauth = build_oauth()
    token_info = refresh_if_needed(oauth, token_info)

    # print("TOKEN AFTER REFRESH:", token_info)

    if not token_info:
        print("REFRESH FAILED")
        return None

    request.session["token_info"] = token_info

    oauth.token_info = token_info
    return spotipy.Spotify(auth_manager=oauth)


@router.get("/callback")
def callback(request: Request):
    oauth = build_oauth()
    code = request.query_params.get("code")

    if not code:
        return JSONResponse({"error": "Missing code"}, status_code=400)

    token_info = oauth.get_access_token(code, check_cache=False)
    request.session["token_info"] = token_info

    sp = spotipy.Spotify(auth_manager=oauth)
    from web.spotify_auth import get_user_id
    user_id = get_user_id(request)
    request.session["user_id"] = user_id

    return RedirectResponse("/dashboard")