from dotenv import load_dotenv
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from .routes import router
from .catalog import initialize_catalog, recover_interrupted_sync_runs
import os

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

APP_ENV = os.getenv("APP_ENV", "development").lower()
IS_PRODUCTION = APP_ENV == "production"
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY")

if IS_PRODUCTION and not SESSION_SECRET_KEY:
    raise RuntimeError("SESSION_SECRET_KEY is required when APP_ENV=production")

app = FastAPI(debug=not IS_PRODUCTION)

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static"
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY or "dev_secret",
    same_site="lax",
    https_only=IS_PRODUCTION,
)

initialize_catalog()
recover_interrupted_sync_runs()
app.include_router(router)
