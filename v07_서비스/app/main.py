"""
v07 서비스 — FastAPI 진입점.
v05가 만든 일자별 데이터를 정보 제공용으로 노출.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.data_loader import (
    find_theme,
    format_date_kr,
    latest_date,
    list_available_dates,
    load_day,
)

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="시황 라운지",
    description="매일 갱신되는 시황 정보 제공 서비스 (투자 자문 아님)",
    version="0.1.0",
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "templates")
templates.env.globals["format_date_kr"] = format_date_kr


def _ctx(request: Request, **kwargs) -> dict:
    """공통 컨텍스트."""
    return {
        "request": request,
        "site_name": "시황 라운지",
        **kwargs,
    }


def _require_day(date: str | None) -> dict:
    """date가 None이면 최신, 존재하지 않으면 404."""
    if date is None:
        date = latest_date()
        if date is None:
            raise HTTPException(status_code=503, detail="아직 생성된 시황 데이터가 없습니다.")
    if date not in list_available_dates():
        raise HTTPException(status_code=404, detail=f"해당 날짜({date})의 데이터가 없습니다.")
    return load_day(date)


# ── 라우트 ───────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    day = _require_day(None)
    return templates.TemplateResponse("home.html", _ctx(request, day=day))


@app.get("/macro", response_class=HTMLResponse)
def macro_page(request: Request):
    day = _require_day(None)
    return templates.TemplateResponse("macro.html", _ctx(request, day=day))


@app.get("/themes", response_class=HTMLResponse)
def themes_index(request: Request):
    day = _require_day(None)
    return templates.TemplateResponse("themes_index.html", _ctx(request, day=day))


@app.get("/themes/{slug}", response_class=HTMLResponse)
def theme_detail(request: Request, slug: str):
    day = _require_day(None)
    theme = find_theme(day["date"], slug)
    if theme is None:
        raise HTTPException(status_code=404, detail=f"테마를 찾을 수 없습니다: {slug}")
    return templates.TemplateResponse(
        "theme_detail.html", _ctx(request, day=day, theme=theme),
    )


@app.get("/archive", response_class=HTMLResponse)
def archive_index(request: Request):
    dates = list_available_dates()
    items = [{"date": d, "label": format_date_kr(d)} for d in dates]
    return templates.TemplateResponse(
        "archive.html", _ctx(request, items=items),
    )


@app.get("/archive/{date}", response_class=HTMLResponse)
def archive_detail(request: Request, date: str):
    day = _require_day(date)
    return templates.TemplateResponse("home.html", _ctx(request, day=day, archive=True))


@app.get("/healthz")
def healthz():
    return {"status": "ok", "latest": latest_date()}
