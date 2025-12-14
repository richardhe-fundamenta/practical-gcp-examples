"""Page routes for BigQuery Data Insight Builder."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/category/{category_id}", response_class=HTMLResponse)
async def category_page(request: Request, category_id: str):
    """Category page - shows all queries in a category."""
    return templates.TemplateResponse(
        "category.html", {"request": request, "category_id": category_id}
    )


@router.get("/editor", response_class=HTMLResponse)
async def editor_page(request: Request, query_id: str = None):
    """Query editor page - create or edit a query."""
    return templates.TemplateResponse(
        "editor.html", {"request": request, "query_id": query_id}
    )


@router.get("/tester/{query_id}", response_class=HTMLResponse)
async def tester_page(request: Request, query_id: str):
    """Query tester page - test a saved query with parameters."""
    return templates.TemplateResponse(
        "tester.html", {"request": request, "query_id": query_id}
    )
