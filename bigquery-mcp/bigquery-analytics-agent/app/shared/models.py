"""Cloud Datastore models for BigQuery Analytics Agent (READ-ONLY).

This is a read-only version of the models used by BigQuery MCP Studio.
The agent only reads query templates and categories from Datastore.
Query management (create/update/delete) is handled by BigQuery MCP Studio.
"""

from datetime import datetime
from typing import Optional

from google.cloud import datastore
from pydantic import BaseModel, Field

from app.config import DATASTORE_DATABASE


class ParameterDefinition(BaseModel):
    """Definition of a SQL query parameter."""

    name: str = Field(..., description="Parameter name (without @ prefix)")
    type: str = Field(
        ...,
        description="BigQuery parameter type (STRING, INT64, FLOAT64, BOOL, DATE, DATETIME, TIMESTAMP)",
    )
    description: str = Field(..., description="Human-readable description")
    required: bool = Field(default=True, description="Whether parameter is required")


class QueryTemplateCreate(BaseModel):
    """Schema for creating a new query template."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1)
    sql_query: str = Field(..., min_length=1)
    parameters: list[ParameterDefinition] = Field(default_factory=list)


class QueryTemplate(QueryTemplateCreate):
    """Full query template with metadata."""

    id: str
    created_at: datetime
    updated_at: datetime
    created_by: str
    version: int = 1


class CategoryCreate(BaseModel):
    """Schema for creating a category."""

    id: str = Field(..., min_length=1, max_length=50, description="URL-safe category ID")
    display_name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="")


class Category(CategoryCreate):
    """Category with query count."""

    query_count: int = 0


class DatastoreClient:
    """Read-only client for Cloud Datastore operations.

    This client only supports reading query templates and categories.
    All write operations (create/update/delete) are handled by BigQuery MCP Studio.
    """

    def __init__(self, project_id: Optional[str] = None):
        """Initialize Datastore client.

        Args:
            project_id: GCP project ID (uses default if not provided)
        """
        self.client = datastore.Client(project=project_id, database=DATASTORE_DATABASE)

    # ===== QueryTemplate Operations (READ-ONLY) =====

    def get_query_template(self, query_id: str) -> Optional[QueryTemplate]:
        """Get a query template by ID.

        Args:
            query_id: Query template ID

        Returns:
            QueryTemplate if found, None otherwise
        """
        key = self.client.key("QueryTemplate", int(query_id))
        entity = self.client.get(key)

        if entity is None:
            return None

        return self._entity_to_query_template(entity)

    def list_query_templates(self, category: Optional[str] = None) -> list[QueryTemplate]:
        """List all query templates, optionally filtered by category.

        Args:
            category: Optional category filter

        Returns:
            List of query templates
        """
        query = self.client.query(kind="QueryTemplate")

        if category:
            query.add_filter("category", "=", category)
            # When filtering by category, fetch all and sort client-side
            # This avoids needing the composite index until it's built
            entities = list(query.fetch())
            # Sort by created_at descending on the client side
            entities.sort(key=lambda e: e.get("created_at"), reverse=True)
        else:
            # When no filter, we can use server-side ordering (single property index)
            query.order = ["-created_at"]
            entities = list(query.fetch())

        return [self._entity_to_query_template(entity) for entity in entities]

    # ===== Category Operations (READ-ONLY) =====

    def get_category(self, category_id: str) -> Optional[Category]:
        """Get a category by ID.

        Args:
            category_id: Category ID

        Returns:
            Category if found, None otherwise
        """
        key = self.client.key("Category", category_id)
        entity = self.client.get(key)

        if entity is None:
            return None

        return self._entity_to_category(entity)

    def list_categories(self) -> list[Category]:
        """List all categories.

        Returns:
            List of all categories
        """
        query = self.client.query(kind="Category")
        query.order = ["display_name"]

        entities = list(query.fetch())
        return [self._entity_to_category(entity) for entity in entities]

    # ===== Helper Methods =====

    def _entity_to_query_template(self, entity: datastore.Entity) -> QueryTemplate:
        """Convert Datastore entity to QueryTemplate.

        Args:
            entity: Datastore entity

        Returns:
            QueryTemplate object
        """
        return QueryTemplate(
            id=str(entity.key.id),
            name=entity["name"],
            description=entity["description"],
            category=entity["category"],
            sql_query=entity["sql_query"],
            parameters=[ParameterDefinition(**p) for p in entity.get("parameters", [])],
            created_at=entity["created_at"],
            updated_at=entity["updated_at"],
            created_by=entity["created_by"],
            version=entity.get("version", 1),
        )

    def _entity_to_category(self, entity: datastore.Entity) -> Category:
        """Convert Datastore entity to Category.

        Args:
            entity: Datastore entity

        Returns:
            Category object
        """
        return Category(
            id=str(entity.key.name),
            display_name=entity["display_name"],
            description=entity.get("description", ""),
            query_count=entity.get("query_count", 0),
        )
