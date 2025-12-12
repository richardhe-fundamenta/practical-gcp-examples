#!/usr/bin/env python3
"""FastAPI web application for managing BigQuery MCP Toolbox queries.

This admin UI provides:
- List/view all queries
- Add new queries
- Edit existing queries
- Enable/disable queries
- Test queries
- Trigger tools.yaml regeneration
"""

import json
import logging
import os

from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from dotenv import load_dotenv

from fastapi import FastAPI, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from google.cloud import bigquery

from utils.bigquery_client import QueryRegistry
from utils.yaml_generator import ToolboxConfigGenerator

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="MCP Toolbox Admin UI", version="1.0.0")

# Setup templates and static files
# Use paths relative to this file's location
BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Add url_for to Jinja2 templates to make it compatible with Flask-style templates
templates.env.globals["url_for"] = app.url_path_for

# Configuration
PROJECT_ID = os.getenv("PROJECT_ID")
REGISTRY_DATASET = os.getenv("REGISTRY_DATASET", "config")
REGISTRY_TABLE = os.getenv("REGISTRY_TABLE", "query_registry")
TOOLS_FILE = os.getenv("TOOLS_FILE", "tools.yaml")
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() in ("true", "1", "yes")
SECRET_NAME = os.getenv("SECRET_NAME", "mcp-tools-yaml")

# Initialize BigQuery client
bq_client = bigquery.Client(project=PROJECT_ID)
registry_table = f"{PROJECT_ID}.{REGISTRY_DATASET}.{REGISTRY_TABLE}"


# Helper function to render toast notifications
def render_toast(message: str, toast_type: str = "success") -> str:
    """Render a toast notification partial.

    Args:
        message: The message to display
        toast_type: Type of toast (success, error, info)

    Returns:
        HTML string for the toast notification
    """
    return templates.get_template("partials/toast.html").render(
        message=message,
        type=toast_type
    )


def get_all_queries() -> list[dict[str, Any]]:
    """Fetch all queries from the registry."""
    query = f"""
    SELECT
        query_name,
        query_category,
        query_sql,
        description,
        parameters,
        enabled,
        created_at,
        updated_at,
        created_by,
        tags,
        estimated_cost_tier,
        max_execution_time_seconds
    FROM `{registry_table}`
    ORDER BY query_category, query_name
    """

    results = bq_client.query(query).result()

    queries = []
    for row in results:
        # Convert parameters to proper JSON format
        params = row.parameters if row.parameters else "[]"
        if params and params != "[]":
            try:
                # Parse and re-serialize to ensure proper JSON format
                params = json.dumps(json.loads(params) if isinstance(params, str) else params)
            except (json.JSONDecodeError, TypeError):
                params = "[]"

        queries.append({
            "query_name": row.query_name,
            "query_category": row.query_category,
            "query_sql": row.query_sql,
            "description": row.description,
            "parameters": params,
            "enabled": row.enabled,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "created_by": row.created_by,
            "tags": row.tags if row.tags else [],
            "estimated_cost_tier": row.estimated_cost_tier,
            "max_execution_time_seconds": row.max_execution_time_seconds,
        })

    return queries


def get_query(query_name: str) -> dict[str, Any] | None:
    """Fetch a single query by name."""
    query = f"""
    SELECT *
    FROM `{registry_table}`
    WHERE query_name = @query_name
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("query_name", "STRING", query_name)
        ]
    )

    results = list(bq_client.query(query, job_config=job_config).result())

    if not results:
        return None

    row = results[0]

    # Convert parameters to proper JSON format
    params = row.parameters if row.parameters else "[]"
    if params and params != "[]":
        try:
            # Parse and re-serialize to ensure proper JSON format
            params = json.dumps(json.loads(params) if isinstance(params, str) else params)
        except (json.JSONDecodeError, TypeError):
            params = "[]"

    return {
        "query_name": row.query_name,
        "query_category": row.query_category,
        "query_sql": row.query_sql,
        "description": row.description,
        "parameters": params,
        "enabled": row.enabled,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "created_by": row.created_by,
        "tags": row.tags if row.tags else [],
        "estimated_cost_tier": row.estimated_cost_tier,
        "max_execution_time_seconds": row.max_execution_time_seconds,
    }


def get_stats() -> dict[str, Any]:
    """Get registry statistics."""
    query = f"""
    SELECT
        COUNT(*) as total,
        SUM(CASE WHEN enabled THEN 1 ELSE 0 END) as enabled_count,
        COUNT(DISTINCT query_category) as categories
    FROM `{registry_table}`
    """

    result = list(bq_client.query(query).result())[0]

    return {
        "total": result.total,
        "enabled": result.enabled_count,
        "disabled": result.total - result.enabled_count,
        "categories": result.categories,
    }


def get_categories() -> list[dict[str, Any]]:
    """Get all categories with their query counts."""
    query = f"""
    SELECT
        query_category,
        COUNT(*) as total_count,
        SUM(CASE WHEN enabled THEN 1 ELSE 0 END) as enabled_count
    FROM `{registry_table}`
    GROUP BY query_category
    ORDER BY query_category
    """

    results = bq_client.query(query).result()

    categories = []
    for row in results:
        categories.append({
            "name": row.query_category,
            "total": row.total_count,
            "enabled": row.enabled_count,
            "disabled": row.total_count - row.enabled_count,
        })

    return categories


def regenerate_tools_yaml() -> tuple[bool, str]:
    """Regenerate tools.yaml configuration and save to Secret Manager or local file.

    In production (DEBUG_MODE=false), saves to Secret Manager.
    In debug mode (DEBUG_MODE=true), saves to local file.

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        logger.info("Triggering tools.yaml regeneration...")
        logger.info(f"Debug mode: {DEBUG_MODE}")

        # Initialize QueryRegistry
        logger.info("Initializing BigQuery client...")
        registry = QueryRegistry(
            project_id=PROJECT_ID,
            dataset=REGISTRY_DATASET,
            table=REGISTRY_TABLE,
        )

        # Fetch queries from registry
        logger.info("Fetching queries from BigQuery registry...")
        queries = registry.get_all_queries()

        if not queries:
            logger.warning("No enabled queries found in registry")
            return True, "Configuration generation skipped (no queries to process)"

        logger.info(f"Successfully fetched {len(queries)} enabled queries")

        # Generate configuration
        logger.info("Generating toolbox configuration...")
        bigquery_source_name = os.getenv("BIGQUERY_SOURCE_NAME", "bigquery-source")
        generator = ToolboxConfigGenerator(
            project_id=PROJECT_ID,
            bigquery_source_name=bigquery_source_name,
        )

        config = generator.generate_config(queries)

        # Validate configuration
        logger.info("Validating generated configuration...")
        if not generator.validate_config(config):
            logger.error("Configuration validation failed")
            return False, "Configuration validation failed"

        logger.info("Configuration validation passed")

        # Save configuration based on mode
        if DEBUG_MODE:
            # Debug mode: Save to local file
            project_root = Path(__file__).parent.parent
            output_file = project_root / TOOLS_FILE
            logger.info(f"[DEBUG MODE] Saving configuration to local file: {output_file}")
            generator.save_config(config, str(output_file))

            # Verify the file was created
            if output_file.exists():
                file_size = output_file.stat().st_size
                logger.info(f"Successfully created {output_file} ({file_size:,} bytes)")
                return True, f"[DEBUG] Configuration saved to {output_file} ({len(queries)} queries)"
            else:
                logger.error(f"Failed to create {output_file}")
                return False, f"Failed to create {output_file}"
        else:
            # Production mode: Save to Secret Manager
            logger.info(f"[PRODUCTION MODE] Saving configuration to Secret Manager: {SECRET_NAME}")
            generator.save_config_to_secret_manager(
                config=config,
                project_id=PROJECT_ID,
                secret_id=SECRET_NAME,
            )
            return True, f"Configuration saved to Secret Manager ({len(queries)} queries)"

    except Exception as e:
        logger.error(f"Error during regeneration: {e}", exc_info=True)
        return False, f"Error: {str(e)}"


@app.get("/", response_class=HTMLResponse, name="index")
async def index(request: Request):
    """Home page - list all categories."""
    categories = get_categories()
    stats = get_stats()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "categories": categories, "stats": stats}
    )


@app.get("/category/{category_name}", response_class=HTMLResponse, name="view_category")
async def view_category(request: Request, category_name: str):
    """View queries for a specific category."""
    # Get queries for this category
    query = f"""
    SELECT
        query_name,
        query_category,
        query_sql,
        description,
        parameters,
        enabled,
        created_at,
        updated_at,
        created_by,
        tags,
        estimated_cost_tier,
        max_execution_time_seconds
    FROM `{registry_table}`
    WHERE query_category = @category
    ORDER BY query_name
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("category", "STRING", category_name)
        ]
    )

    results = bq_client.query(query, job_config=job_config).result()

    queries = []
    for row in results:
        # Convert parameters to proper JSON format
        params = row.parameters if row.parameters else "[]"
        if params and params != "[]":
            try:
                params = json.dumps(json.loads(params) if isinstance(params, str) else params)
            except (json.JSONDecodeError, TypeError):
                params = "[]"

        queries.append({
            "query_name": row.query_name,
            "query_category": row.query_category,
            "query_sql": row.query_sql,
            "description": row.description,
            "parameters": params,
            "enabled": row.enabled,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "created_by": row.created_by,
            "tags": row.tags if row.tags else [],
            "estimated_cost_tier": row.estimated_cost_tier,
            "max_execution_time_seconds": row.max_execution_time_seconds,
        })

    stats = get_stats()

    return templates.TemplateResponse(
        "category.html",
        {"request": request, "category": category_name, "queries": queries, "stats": stats}
    )


@app.get("/query/new", response_class=HTMLResponse, name="new_query_form")
async def new_query_form(request: Request):
    """Display new query form."""
    return templates.TemplateResponse(
        "edit_query.html",
        {"request": request, "query": None, "mode": "new"}
    )


@app.post("/query/new")
async def new_query(
    request: Request,
    query_name: str = Form(...),
    query_category: str = Form(...),
    query_sql: str = Form(...),
    description: str = Form(...),
    parameters: str = Form("[]"),
    enabled: Optional[str] = Form(None),
    created_by: str = Form("admin"),
    tags: str = Form(""),
    estimated_cost_tier: str = Form("MEDIUM"),
    max_execution_time_seconds: str = Form(""),
):
    """Create a new query."""
    try:
        # Validate parameters JSON
        try:
            json.loads(parameters)
        except json.JSONDecodeError:
            # Return toast notification for HTMX
            return Response(
                content=render_toast("Invalid JSON in parameters field", "error"),
                media_type="text/html",
                headers={"HX-Retarget": "#toast-container", "HX-Reswap": "beforeend"}
            )

        # Parse tags and enabled
        tags_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
        enabled_bool = enabled == "on"

        # Insert into BigQuery
        insert_query = f"""
        INSERT INTO `{registry_table}` (
            query_name,
            query_category,
            query_sql,
            description,
            parameters,
            enabled,
            created_at,
            updated_at,
            created_by,
            tags,
            estimated_cost_tier,
            max_execution_time_seconds
        ) VALUES (
            @query_name,
            @query_category,
            @query_sql,
            @description,
            PARSE_JSON(@parameters),
            @enabled,
            CURRENT_TIMESTAMP(),
            CURRENT_TIMESTAMP(),
            @created_by,
            @tags,
            @estimated_cost_tier,
            @max_execution_time
        )
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("query_name", "STRING", query_name),
                bigquery.ScalarQueryParameter("query_category", "STRING", query_category),
                bigquery.ScalarQueryParameter("query_sql", "STRING", query_sql),
                bigquery.ScalarQueryParameter("description", "STRING", description),
                bigquery.ScalarQueryParameter("parameters", "STRING", parameters),
                bigquery.ScalarQueryParameter("enabled", "BOOL", enabled_bool),
                bigquery.ScalarQueryParameter("created_by", "STRING", created_by),
                bigquery.ArrayQueryParameter("tags", "STRING", tags_list),
                bigquery.ScalarQueryParameter("estimated_cost_tier", "STRING", estimated_cost_tier),
                bigquery.ScalarQueryParameter("max_execution_time", "INTEGER", int(max_execution_time_seconds) if max_execution_time_seconds else None),
            ]
        )

        bq_client.query(insert_query, job_config=job_config).result()

        # Return toast + redirect using HTMX
        toast = render_toast(f"Query '{query_name}' created successfully!", "success")
        return Response(
            content=toast,
            media_type="text/html",
            headers={
                "HX-Retarget": "#toast-container",
                "HX-Reswap": "beforeend",
                "HX-Redirect": f"/query/{query_name}"
            }
        )

    except Exception as e:
        logger.error(f"Error creating query: {e}")
        return Response(
            content=render_toast(f"Error creating query: {str(e)}", "error"),
            media_type="text/html",
            headers={"HX-Retarget": "#toast-container", "HX-Reswap": "beforeend"}
        )


@app.get("/query/{query_name}/edit", response_class=HTMLResponse, name="edit_query")
async def edit_query_form(request: Request, query_name: str):
    """Display edit query form."""
    query = get_query(query_name)
    if not query:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        "edit_query.html",
        {"request": request, "query": query, "mode": "edit"}
    )


@app.post("/query/{query_name}/edit")
async def edit_query(
    request: Request,
    query_name: str,
    query_category: str = Form(...),
    query_sql: str = Form(...),
    description: str = Form(...),
    parameters: str = Form("[]"),
    enabled: Optional[str] = Form(None),
    tags: str = Form(""),
    estimated_cost_tier: str = Form("MEDIUM"),
    max_execution_time_seconds: str = Form(""),
):
    """Edit an existing query."""
    try:
        # Validate parameters JSON
        try:
            json.loads(parameters)
        except json.JSONDecodeError:
            return Response(
                content=render_toast("Invalid JSON in parameters field", "error"),
                media_type="text/html",
                headers={"HX-Retarget": "#toast-container", "HX-Reswap": "beforeend"}
            )

        # Parse tags and enabled
        tags_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
        enabled_bool = enabled == "on"

        # Update in BigQuery
        update_query = f"""
        UPDATE `{registry_table}`
        SET
            query_category = @query_category,
            query_sql = @query_sql,
            description = @description,
            parameters = PARSE_JSON(@parameters),
            enabled = @enabled,
            updated_at = CURRENT_TIMESTAMP(),
            tags = @tags,
            estimated_cost_tier = @estimated_cost_tier,
            max_execution_time_seconds = @max_execution_time
        WHERE query_name = @query_name
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("query_name", "STRING", query_name),
                bigquery.ScalarQueryParameter("query_category", "STRING", query_category),
                bigquery.ScalarQueryParameter("query_sql", "STRING", query_sql),
                bigquery.ScalarQueryParameter("description", "STRING", description),
                bigquery.ScalarQueryParameter("parameters", "STRING", parameters),
                bigquery.ScalarQueryParameter("enabled", "BOOL", enabled_bool),
                bigquery.ArrayQueryParameter("tags", "STRING", tags_list),
                bigquery.ScalarQueryParameter("estimated_cost_tier", "STRING", estimated_cost_tier),
                bigquery.ScalarQueryParameter("max_execution_time", "INTEGER", int(max_execution_time_seconds) if max_execution_time_seconds else None),
            ]
        )

        bq_client.query(update_query, job_config=job_config).result()

        # Return toast + redirect using HTMX
        toast = render_toast(f"Query '{query_name}' updated successfully!", "success")
        return Response(
            content=toast,
            media_type="text/html",
            headers={
                "HX-Retarget": "#toast-container",
                "HX-Reswap": "beforeend",
                "HX-Redirect": f"/query/{query_name}"
            }
        )

    except Exception as e:
        logger.error(f"Error updating query: {e}")
        return Response(
            content=render_toast(f"Error updating query: {str(e)}", "error"),
            media_type="text/html",
            headers={"HX-Retarget": "#toast-container", "HX-Reswap": "beforeend"}
        )


@app.post("/query/{query_name}/toggle")
async def toggle_query(query_name: str):
    """Toggle query enabled/disabled state."""
    try:
        query = get_query(query_name)
        if not query:
            return JSONResponse(
                {"success": False, "error": "Query not found"},
                status_code=status.HTTP_404_NOT_FOUND
            )

        new_state = not query["enabled"]

        update_query = f"""
        UPDATE `{registry_table}`
        SET enabled = @enabled, updated_at = CURRENT_TIMESTAMP()
        WHERE query_name = @query_name
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("query_name", "STRING", query_name),
                bigquery.ScalarQueryParameter("enabled", "BOOL", new_state),
            ]
        )

        bq_client.query(update_query, job_config=job_config).result()

        return JSONResponse({"success": True, "enabled": new_state})

    except Exception as e:
        logger.error(f"Error toggling query: {e}")
        return JSONResponse(
            {"success": False, "error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@app.post("/query/{query_name}/delete")
async def delete_query(request: Request, query_name: str):
    """Delete a query."""
    try:
        delete_query_sql = f"""
        DELETE FROM `{registry_table}`
        WHERE query_name = @query_name
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("query_name", "STRING", query_name),
            ]
        )

        bq_client.query(delete_query_sql, job_config=job_config).result()

        # Return toast + redirect using HTMX
        toast = render_toast(f"Query '{query_name}' deleted successfully!", "success")
        return Response(
            content=toast,
            media_type="text/html",
            headers={
                "HX-Retarget": "#toast-container",
                "HX-Reswap": "beforeend",
                "HX-Redirect": "/"
            }
        )

    except Exception as e:
        logger.error(f"Error deleting query: {e}")
        return Response(
            content=render_toast(f"Error deleting query: {str(e)}", "error"),
            media_type="text/html",
            headers={"HX-Retarget": "#toast-container", "HX-Reswap": "beforeend"}
        )


@app.get("/query/{query_name}", response_class=HTMLResponse, name="view_query")
async def view_query(request: Request, query_name: str):
    """View a single query."""
    query = get_query(query_name)
    if not query:
        # Return 404 page with error message
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "queries": get_all_queries(), "stats": get_stats(),
             "error": f"Query '{query_name}' not found"},
            status_code=status.HTTP_404_NOT_FOUND
        )

    return templates.TemplateResponse(
        "view_query.html",
        {"request": request, "query": query}
    )


@app.post("/api/reload")
async def api_reload():
    """API endpoint to trigger tools.yaml regeneration."""
    success, message = regenerate_tools_yaml()

    if success:
        return JSONResponse({"success": True, "message": message})
    else:
        return JSONResponse(
            {"success": False, "error": message},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@app.post("/reload", name="reload")
async def reload(request: Request):
    """Trigger tools.yaml regeneration from UI."""
    success, message = regenerate_tools_yaml()

    toast_type = "success" if success else "error"
    return Response(
        content=render_toast(message, toast_type),
        media_type="text/html",
        headers={"HX-Retarget": "#toast-container", "HX-Reswap": "beforeend"}
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return JSONResponse({"status": "healthy", "service": "admin-ui"})


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", os.getenv("ADMIN_PORT", "8080")))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
