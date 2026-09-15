from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from web.templates_config import templates

router = APIRouter()

@router.get("/")
def root(request: Request):
    return RedirectResponse("/dashboard")


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    if not request.session.get("token_info"):
        return RedirectResponse("/login")
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get("/workspace", response_class=HTMLResponse)
def workspace(request: Request):
    if not request.session.get("token_info"):
        return RedirectResponse("/login")
    return templates.TemplateResponse("workspace.html", {"request": request})


@router.get("/health", response_class=HTMLResponse)
def health(request: Request):
    if not request.session.get("token_info"):
        return RedirectResponse("/login")
    return templates.TemplateResponse("health.html", {"request": request})


@router.get("/recommendations", response_class=HTMLResponse)
def recommendations(request: Request):
    if not request.session.get("token_info"):
        return RedirectResponse("/login")
    return templates.TemplateResponse("recommendations.html", {"request": request})
