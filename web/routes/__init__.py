from fastapi import APIRouter

from .auth import router as auth_router
from .pages import router as pages_router
from .playlists import router as playlists_router
from .library import router as library_router
from .nav import router as nav_router
from .analytics import router as analytics_router
from .recommendations import router as recommendations_router
from .sync import router as sync_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(pages_router)
router.include_router(playlists_router)
router.include_router(library_router)
router.include_router(nav_router)
router.include_router(analytics_router)
router.include_router(recommendations_router)
router.include_router(sync_router)
