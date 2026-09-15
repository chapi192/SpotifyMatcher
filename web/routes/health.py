from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from web.catalog import library_health
from web.spotify_auth import get_user_id


router = APIRouter()


@router.get("/api/health")
def health_report(request: Request, limit: int = 250):
    if not request.session.get("token_info"):
        return JSONResponse({"error": "Not logged in"}, status_code=401)
    user_id = get_user_id(request)
    if not user_id:
        return JSONResponse({"error": "Spotify session is incomplete"}, status_code=401)
    return library_health(user_id, limit)
