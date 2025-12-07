#!/usr/bin/env python3
"""Populate the BigQuery registry with sample queries.

This script reads the sample_queries.sql file and executes it
to populate the query registry table.

Script will use REGISTRY_DATASET and REGISTRY_TABLE from env vars.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import bigquery


def main() -> int:
    """Main entry point."""
    # Load environment variables from .env file
    load_dotenv()

    # Get configuration from environment variables
    project_id = os.getenv("PROJECT_ID")
    dataset = os.getenv("REGISTRY_DATASET", "config")
    table = os.getenv("REGISTRY_TABLE", "query_registry")
    sql_file_path = os.getenv("SQL_FILE", "config/sample_queries.sql")

    if not project_id:
        print("ERROR: Project ID is required. Set PROJECT_ID env var")
        return 1

    # Check if SQL file exists
    sql_file = Path(sql_file_path)
    if not sql_file.exists():
        print(f"ERROR: SQL file not found: {sql_file_path}")
        return 1

    print("=" * 70)
    print("Populating BigQuery Registry with Sample Queries")
    print("=" * 70)
    print(f"Project ID: {project_id}")
    print(f"Dataset: {dataset}")
    print(f"Table: {table}")
    print(f"SQL File: {sql_file_path}")
    print("=" * 70)

    # Read SQL file
    print(f"Reading SQL file: {sql_file_path}")
    with open(sql_file, "r") as f:
        sql_content = f.read()

    # Substitute environment variables in SQL
    print("Substituting environment variables...")
    sql_content = sql_content.replace("${REGISTRY_DATASET}", dataset)
    sql_content = sql_content.replace("${REGISTRY_TABLE}", table)

    # Initialize BigQuery client
    print("Initializing BigQuery client...")
    client = bigquery.Client(project=project_id)

    # Split by INSERT statements (simple approach)
    # For more complex SQL parsing, consider using sqlparse library
    statements = [s.strip() for s in sql_content.split("INSERT INTO") if s.strip()]

    print(f"Found {len(statements)} INSERT statements")
    print("=" * 70)

    # Execute each statement
    success_count = 0
    error_count = 0

    for i, statement in enumerate(statements, 1):
        # Reconstruct the INSERT statement
        # Check if this looks like our registry table
        registry_ref = f"{dataset}.{table}".upper()
        if not statement.upper().startswith(registry_ref):
            continue

        full_statement = f"INSERT INTO {statement}"

        print(f"\nExecuting statement {i}/{len(statements)}...")

        try:
            query_job = client.query(full_statement)
            query_job.result()  # Wait for completion
            print(f"✓ Statement {i} executed successfully")
            success_count += 1
        except Exception as e:
            print(f"✗ Statement {i} failed: {e}")
            error_count += 1

    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"Successful: {success_count}")
    print(f"Failed: {error_count}")
    print("=" * 70)

    # Verify the data
    print("\nVerifying inserted queries...")
    verify_query = f"""
    SELECT query_category, COUNT(*) as count
    FROM {dataset}.{table}
    WHERE enabled = true
    GROUP BY query_category
    ORDER BY query_category
    """

    try:
        result = client.query(verify_query).result()
        print("\nQueries by category:")
        for row in result:
            print(f"  - {row.query_category}: {row.count}")
    except Exception as e:
        print(f"Warning: Could not verify data: {e}")

    print("\n" + "=" * 70)
    if error_count == 0:
        print("All sample queries populated successfully!")
    else:
        print(f"Completed with {error_count} errors")
    print("=" * 70)

    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
