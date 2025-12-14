"""Cloud Datastore models for BigQuery MCP Studio."""

from datetime import datetime
from typing import Any, Optional

from google.cloud import datastore
from pydantic import BaseModel, Field


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
    """Client for Cloud Datastore operations."""

    def __init__(self, project_id: Optional[str] = None):
        """Initialize Datastore client."""
        self.client = datastore.Client(project=project_id)

    # ===== QueryTemplate Operations =====

    def create_query_template(
        self, template: QueryTemplateCreate, created_by: str
    ) -> QueryTemplate:
        """Create a new query template."""
        key = self.client.key("QueryTemplate")
        entity = datastore.Entity(key=key)

        now = datetime.utcnow()
        entity.update(
            {
                "name": template.name,
                "description": template.description,
                "category": template.category,
                "sql_query": template.sql_query,
                "parameters": [p.model_dump() for p in template.parameters],
                "created_at": now,
                "updated_at": now,
                "created_by": created_by,
                "version": 1,
            }
        )

        self.client.put(entity)

        # Update category query count
        self._increment_category_count(template.category)

        return self._entity_to_query_template(entity)

    def get_query_template(self, query_id: str) -> Optional[QueryTemplate]:
        """Get a query template by ID."""
        key = self.client.key("QueryTemplate", int(query_id))
        entity = self.client.get(key)

        if entity is None:
            return None

        return self._entity_to_query_template(entity)

    def update_query_template(
        self, query_id: str, template: QueryTemplateCreate, updated_by: str
    ) -> Optional[QueryTemplate]:
        """Update an existing query template."""
        key = self.client.key("QueryTemplate", int(query_id))
        entity = self.client.get(key)

        if entity is None:
            return None

        old_category = entity.get("category")
        new_category = template.category

        entity.update(
            {
                "name": template.name,
                "description": template.description,
                "category": new_category,
                "sql_query": template.sql_query,
                "parameters": [p.model_dump() for p in template.parameters],
                "updated_at": datetime.utcnow(),
                "version": entity.get("version", 1) + 1,
            }
        )

        self.client.put(entity)

        # Update category counts if category changed
        if old_category != new_category:
            self._decrement_category_count(old_category)
            self._increment_category_count(new_category)

        return self._entity_to_query_template(entity)

    def delete_query_template(self, query_id: str) -> bool:
        """Delete a query template."""
        key = self.client.key("QueryTemplate", int(query_id))
        entity = self.client.get(key)

        if entity is None:
            return False

        category = entity.get("category")
        self.client.delete(key)

        # Update category query count
        self._decrement_category_count(category)

        return True

    def list_query_templates(self, category: Optional[str] = None) -> list[QueryTemplate]:
        """List all query templates, optionally filtered by category."""
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

    # ===== Category Operations =====

    def create_category(self, category: CategoryCreate) -> Category:
        """Create a new category."""
        key = self.client.key("Category", category.id)
        entity = datastore.Entity(key=key)

        entity.update(
            {
                "display_name": category.display_name,
                "description": category.description,
                "query_count": 0,
            }
        )

        self.client.put(entity)
        return self._entity_to_category(entity)

    def get_category(self, category_id: str) -> Optional[Category]:
        """Get a category by ID."""
        key = self.client.key("Category", category_id)
        entity = self.client.get(key)

        if entity is None:
            return None

        return self._entity_to_category(entity)

    def list_categories(self) -> list[Category]:
        """List all categories."""
        query = self.client.query(kind="Category")
        query.order = ["display_name"]

        entities = list(query.fetch())
        return [self._entity_to_category(entity) for entity in entities]

    def _increment_category_count(self, category_id: str) -> None:
        """Increment query count for a category."""
        key = self.client.key("Category", category_id)
        entity = self.client.get(key)

        if entity is None:
            # Create category if it doesn't exist
            entity = datastore.Entity(key=key)
            entity["display_name"] = category_id.replace("_", " ").title()
            entity["description"] = ""
            entity["query_count"] = 0

        entity["query_count"] = entity.get("query_count", 0) + 1
        self.client.put(entity)

    def _decrement_category_count(self, category_id: str) -> None:
        """Decrement query count for a category."""
        key = self.client.key("Category", category_id)
        entity = self.client.get(key)

        if entity:
            entity["query_count"] = max(0, entity.get("query_count", 0) - 1)
            self.client.put(entity)

    # ===== Helper Methods =====

    def _entity_to_query_template(self, entity: datastore.Entity) -> QueryTemplate:
        """Convert Datastore entity to QueryTemplate."""
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
        """Convert Datastore entity to Category."""
        return Category(
            id=str(entity.key.name),
            display_name=entity["display_name"],
            description=entity.get("description", ""),
            query_count=entity.get("query_count", 0),
        )
