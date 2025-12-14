"""API routes for BigQuery MCP Studio."""

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.models import CategoryCreate, QueryTemplateCreate

router = APIRouter(tags=["api"])
logger = logging.getLogger(__name__)


# ===== Request/Response Models =====


class GenerateSQLRequest(BaseModel):
    """Request to generate SQL from natural language."""

    description: str


class GenerateSQLResponse(BaseModel):
    """Response with generated SQL and parameters."""

    sql: str
    parameters: list[dict[str, Any]]


class ValidateQueryRequest(BaseModel):
    """Request to validate a query."""

    sql_query: str
    test_parameters: dict[str, Any]


class ValidateQueryResponse(BaseModel):
    """Response from query validation."""

    valid: bool
    results: Optional[str] = None
    error: Optional[str] = None
    row_count: Optional[int] = None
    executed_query: Optional[str] = None


class ExecuteQueryRequest(BaseModel):
    """Request to execute a query."""

    query_id: str
    parameters: dict[str, Any]
    max_results: int = 100


# ===== Category Routes =====


@router.get("/categories")
async def list_categories(request: Request):
    """List all categories."""
    datastore = request.app.state.datastore
    categories = datastore.list_categories()
    return {"categories": [cat.model_dump() for cat in categories]}


@router.post("/categories")
async def create_category(request: Request, category: CategoryCreate):
    """Create a new category."""
    datastore = request.app.state.datastore

    # Check if category already exists
    existing = datastore.get_category(category.id)
    if existing:
        raise HTTPException(status_code=400, detail="Category already exists")

    created = datastore.create_category(category)
    return {"category": created.model_dump()}


@router.get("/categories/{category_id}")
async def get_category(request: Request, category_id: str):
    """Get a specific category."""
    datastore = request.app.state.datastore
    category = datastore.get_category(category_id)

    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    return {"category": category.model_dump()}


# ===== Query Template Routes =====


@router.get("/queries")
async def list_queries(request: Request, category: Optional[str] = None):
    """List all query templates, optionally filtered by category."""
    datastore = request.app.state.datastore
    queries = datastore.list_query_templates(category=category)
    return {"queries": [q.model_dump() for q in queries]}


@router.get("/queries/{query_id}")
async def get_query(request: Request, query_id: str):
    """Get a specific query template."""
    datastore = request.app.state.datastore
    query = datastore.get_query_template(query_id)

    if not query:
        raise HTTPException(status_code=404, detail="Query not found")

    return {"query": query.model_dump()}


@router.post("/queries")
async def create_query(request: Request, template: QueryTemplateCreate):
    """Create a new query template."""
    datastore = request.app.state.datastore

    # For now, use a default user email (in production, get from authentication)
    created_by = "user@example.com"

    created = datastore.create_query_template(template, created_by=created_by)
    return {"query": created.model_dump()}


@router.put("/queries/{query_id}")
async def update_query(request: Request, query_id: str, template: QueryTemplateCreate):
    """Update an existing query template."""
    datastore = request.app.state.datastore

    updated_by = "user@example.com"
    updated = datastore.update_query_template(query_id, template, updated_by=updated_by)

    if not updated:
        raise HTTPException(status_code=404, detail="Query not found")

    return {"query": updated.model_dump()}


@router.delete("/queries/{query_id}")
async def delete_query(request: Request, query_id: str):
    """Delete a query template."""
    datastore = request.app.state.datastore
    success = datastore.delete_query_template(query_id)

    if not success:
        raise HTTPException(status_code=404, detail="Query not found")

    return {"success": True}


# ===== MCP Integration Routes =====


@router.post("/mcp/generate-sql", response_model=GenerateSQLResponse)
async def generate_sql(request: Request, req: GenerateSQLRequest):
    """Generate SQL from natural language description using MCP."""
    logger.info(f"Received generate-sql request: {req.description}")
    mcp_service = request.app.state.mcp_service

    try:
        logger.debug("Calling MCP service to generate SQL")
        result = await mcp_service.generate_sql_from_natural_language(req.description)
        logger.info("SQL generated successfully")
        return GenerateSQLResponse(sql=result["sql"], parameters=result["parameters"])
    except Exception as e:
        logger.error(f"Error generating SQL: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mcp/validate-query", response_model=ValidateQueryResponse)
async def validate_query(request: Request, req: ValidateQueryRequest):
    """Validate a query by executing it with test parameters."""
    mcp_service = request.app.state.mcp_service

    result = await mcp_service.validate_and_test_query(req.sql_query, req.test_parameters)

    return ValidateQueryResponse(
        valid=result["valid"],
        results=result.get("results"),
        error=result.get("error"),
        row_count=result.get("row_count"),
        executed_query=result.get("executed_query"),
    )


@router.post("/mcp/execute-query")
async def execute_query(request: Request, req: ExecuteQueryRequest):
    """Execute a saved query with parameters."""
    datastore = request.app.state.datastore
    mcp_service = request.app.state.mcp_service

    # Get the query template
    query = datastore.get_query_template(req.query_id)
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")

    # Execute the query
    result = await mcp_service.execute_query(
        query.sql_query, req.parameters, max_results=req.max_results
    )

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])

    return {"results": result["results"]}
