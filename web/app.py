from dotenv import load_dotenv
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from .routes import router
import os

# force load env
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)

# check if env is loaded
print("CWD:", os.getcwd())
print("CLIENT:", os.getenv("SPOTIFY_CLIENT_ID"))

# debug on 
app = FastAPI(debug=True)

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static"
)

# part of Oauth
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "dev_secret")
)

# include routes
app.include_router(router)