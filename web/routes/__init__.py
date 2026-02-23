from fastapi import APIRouter

from .auth import router as auth_router
from .pages import router as pages_router
from .playlists import router as playlists_router
from .build import router as build_router
from .library import router as library_router
from .nav import router as nav_router
from .analytics import router as analytics_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(pages_router)
router.include_router(playlists_router)
router.include_router(build_router)
router.include_router(library_router)
router.include_router(nav_router)
router.include_router(analytics_router)