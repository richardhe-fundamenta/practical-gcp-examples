"""BigQuery client utilities for querying the registry table."""

import json
import logging
from typing import Any

from google.cloud import bigquery
from google.api_core import retry

logger = logging.getLogger(__name__)


class QueryRegistry:
    """Client for interacting with the BigQuery query registry."""

    def __init__(
        self,
        project_id: str,
        dataset: str = "config",
        table: str = "query_registry",
    ):
        """Initialize the QueryRegistry client.

        Args:
            project_id: GCP project ID
            dataset: BigQuery dataset name containing the registry
            table: Table name for the query registry
        """
        self.project_id = project_id
        self.dataset = dataset
        self.table = table
        self.client = bigquery.Client(project=project_id)
        self.registry_table = f"{project_id}.{dataset}.{table}"

    @retry.Retry(predicate=retry.if_transient_error)
    def get_all_queries(self) -> list[dict[str, Any]]:
        """Fetch all enabled queries from the registry.

        Returns:
            List of query dictionaries with all registry fields

        Raises:
            google.cloud.exceptions.GoogleCloudError: If query fails
        """
        query = f"""
        SELECT
            query_name,
            query_category,
            query_sql,
            description,
            parameters,
            enabled,
            created_at,
            updated_at
        FROM `{self.registry_table}`
        WHERE enabled = true
        ORDER BY query_category, query_name
        """

        logger.info(f"Fetching queries from {self.registry_table}")

        try:
            query_job = self.client.query(query)
            results = query_job.result()

            queries = []
            for row in results:
                # Parse parameters JSON if present
                parameters = []
                if row.parameters:
                    try:
                        # Check if parameters is already a list/dict or if it's a string
                        if isinstance(row.parameters, (list, dict)):
                            parameters = row.parameters
                        else:
                            parameters = json.loads(row.parameters)
                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"Invalid JSON in parameters for {row.query_name}: {e}"
                        )
                        parameters = []

                queries.append(
                    {
                        "query_name": row.query_name,
                        "query_category": row.query_category,
                        "query_sql": row.query_sql,
                        "description": row.description,
                        "parameters": parameters,
                        "enabled": row.enabled,
                        "created_at": row.created_at,
                        "updated_at": row.updated_at,
                    }
                )

            logger.info(f"Successfully fetched {len(queries)} queries")
            return queries

        except Exception as e:
            logger.error(f"Failed to fetch queries from registry: {e}")
            raise

    def get_queries_by_category(self, category: str) -> list[dict[str, Any]]:
        """Fetch queries filtered by category.

        Args:
            category: The category to filter by

        Returns:
            List of query dictionaries for the specified category
        """
        query = f"""
        SELECT
            query_name,
            query_category,
            query_sql,
            description,
            parameters,
            enabled,
            created_at,
            updated_at
        FROM `{self.registry_table}`
        WHERE enabled = true
          AND query_category = @category
        ORDER BY query_name
        """

        logger.info(f"Fetching {category} queries from {self.registry_table}")

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("category", "STRING", category)
            ]
        )

        try:
            query_job = self.client.query(query, job_config=job_config)
            results = query_job.result()

            queries = []
            for row in results:
                parameters = []
                if row.parameters:
                    try:
                        # Check if parameters is already a list/dict or if it's a string
                        if isinstance(row.parameters, (list, dict)):
                            parameters = row.parameters
                        else:
                            parameters = json.loads(row.parameters)
                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"Invalid JSON in parameters for {row.query_name}: {e}"
                        )

                queries.append(
                    {
                        "query_name": row.query_name,
                        "query_category": row.query_category,
                        "query_sql": row.query_sql,
                        "description": row.description,
                        "parameters": parameters,
                        "enabled": row.enabled,
                        "created_at": row.created_at,
                        "updated_at": row.updated_at,
                    }
                )

            logger.info(f"Successfully fetched {len(queries)} {category} queries")
            return queries

        except Exception as e:
            logger.error(f"Failed to fetch {category} queries: {e}")
            raise

    def get_registry_stats(self) -> dict[str, Any]:
        """Get statistics about the query registry.

        Returns:
            Dictionary with registry statistics
        """
        query = f"""
        SELECT
            COUNT(*) as total_queries,
            SUM(CASE WHEN enabled THEN 1 ELSE 0 END) as enabled_queries,
            COUNT(DISTINCT query_category) as categories,
            query_category,
            COUNT(*) as category_count
        FROM `{self.registry_table}`
        GROUP BY query_category
        """

        try:
            query_job = self.client.query(query)
            results = query_job.result()

            stats = {
                "total_queries": 0,
                "enabled_queries": 0,
                "categories": 0,
                "by_category": {},
            }

            for row in results:
                if row.query_category:
                    stats["by_category"][row.query_category] = row.category_count

            # Get overall stats
            overall_query = f"""
            SELECT
                COUNT(*) as total_queries,
                SUM(CASE WHEN enabled THEN 1 ELSE 0 END) as enabled_queries,
                COUNT(DISTINCT query_category) as categories
            FROM `{self.registry_table}`
            """

            overall_job = self.client.query(overall_query)
            overall_result = list(overall_job.result())[0]

            stats["total_queries"] = overall_result.total_queries
            stats["enabled_queries"] = overall_result.enabled_queries
            stats["categories"] = overall_result.categories

            return stats

        except Exception as e:
            logger.error(f"Failed to get registry stats: {e}")
            raise
