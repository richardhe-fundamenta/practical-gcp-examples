"""Main FastAPI application for BigQuery MCP Studio."""

import logging
import os
import traceback
from contextlib import asynccontextmanager

import google.auth
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.models import DatastoreClient
from app.mcp_service import MCPService
from app.routes import api, pages

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup: Initialize services
    _, project_id = google.auth.default()
    os.environ["GOOGLE_CLOUD_PROJECT"] = project_id

    app.state.datastore = DatastoreClient(project_id=project_id)
    app.state.mcp_service = MCPService()
    app.state.project_id = project_id

    yield

    # Shutdown: cleanup if needed
    pass


app = FastAPI(
    title="BigQuery MCP Studio",
    description="GUI for creating and maintaining parameterized BigQuery SQL queries",
    version="0.1.0",
    lifespan=lifespan,
    debug=True,
)


# Global exception handler for debugging
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler to log and return detailed errors."""
    logger.error(f"Unhandled exception: {exc}")
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "type": type(exc).__name__,
            "traceback": traceback.format_exc().split("\n"),
        },
    )

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="app/templates")

# Include routers
app.include_router(api.router, prefix="/api")
app.include_router(pages.router)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page - shows category grid."""
    return templates.TemplateResponse("home.html", {"request": request})


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
