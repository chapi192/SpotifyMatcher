from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from web.templates_config import templates

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
def landing(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request})


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    if not request.session.get("token_info"):
        return RedirectResponse("/login")
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get("/workspace", response_class=HTMLResponse)
def workspace(request: Request):
    return templates.TemplateResponse("workspace.html", {"request": request})


@router.get("/recommendations", response_class=HTMLResponse)
def recommendations(request: Request):
    return templates.TemplateResponse("recommendations.html", {"request": request})