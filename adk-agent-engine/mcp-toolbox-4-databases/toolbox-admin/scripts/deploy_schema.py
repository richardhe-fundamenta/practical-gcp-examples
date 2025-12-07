#!/usr/bin/env python3
"""Deploy the BigQuery schema for the query registry.

This script reads the schema.sql file, substitutes environment variables,
and executes it to create the dataset and table structure.
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import bigquery


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Deploy BigQuery schema for query registry"
    )

    parser.add_argument(
        "--project-id",
        type=str,
        default=os.getenv("PROJECT_ID"),
        help="GCP Project ID (default: from PROJECT_ID env var)",
    )

    parser.add_argument(
        "--dataset",
        type=str,
        default=os.getenv("REGISTRY_DATASET", "config"),
        help="BigQuery dataset containing registry table (default: config)",
    )

    parser.add_argument(
        "--table",
        type=str,
        default=os.getenv("REGISTRY_TABLE", "query_registry"),
        help="BigQuery table name for query registry (default: query_registry)",
    )

    parser.add_argument(
        "--schema-file",
        type=str,
        default="config/schema.sql",
        help="Path to SQL schema file (default: config/schema.sql)",
    )

    parser.add_argument(
        "--region",
        type=str,
        default=os.getenv("REGION", "us-central1"),
        help="BigQuery region (default: us-central1)",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    # Load environment variables from .env file
    load_dotenv()

    args = parse_args()

    if not args.project_id:
        print("ERROR: Project ID is required. Set PROJECT_ID env var or use --project-id")
        return 1

    # Check if schema file exists
    schema_file = Path(args.schema_file)
    if not schema_file.exists():
        print(f"ERROR: Schema file not found: {args.schema_file}")
        return 1

    print("=" * 70)
    print("Deploying BigQuery Schema")
    print("=" * 70)
    print(f"Project ID: {args.project_id}")
    print(f"Dataset: {args.dataset}")
    print(f"Table: {args.table}")
    print(f"Region: {args.region}")
    print(f"Schema File: {args.schema_file}")
    print("=" * 70)

    # Read schema file
    print(f"\nReading schema file: {args.schema_file}")
    with open(schema_file, "r") as f:
        schema_sql = f.read()

    # Substitute environment variables in SQL
    print("Substituting environment variables...")
    schema_sql = schema_sql.replace("${REGISTRY_DATASET}", args.dataset)
    schema_sql = schema_sql.replace("${REGISTRY_TABLE}", args.table)
    schema_sql = schema_sql.replace("us-central1", args.region)  # Replace default region

    # Initialize BigQuery client
    print("Initializing BigQuery client...")
    client = bigquery.Client(project=args.project_id)

    # Split the SQL into individual statements
    # BigQuery client can't execute multiple statements at once
    statements = []

    # Split by semicolons, but be careful with comments
    current_statement = []
    in_comment = False

    for line in schema_sql.split('\n'):
        stripped = line.strip()

        # Skip comment lines
        if stripped.startswith('--'):
            continue

        # Handle multi-line comments
        if '/*' in stripped:
            in_comment = True
        if '*/' in stripped:
            in_comment = False
            continue

        if in_comment:
            continue

        # Add non-empty lines to current statement
        if stripped:
            current_statement.append(line)

        # If line ends with semicolon, we have a complete statement
        if stripped.endswith(';'):
            statement = '\n'.join(current_statement).rstrip(';').strip()
            if statement:
                statements.append(statement)
            current_statement = []

    print(f"\nFound {len(statements)} SQL statements to execute")
    print("=" * 70)

    # Execute each statement
    success_count = 0
    error_count = 0

    for i, statement in enumerate(statements, 1):
        print(f"\nExecuting statement {i}/{len(statements)}...")

        # Show first line of statement for context
        first_line = statement.split('\n')[0][:80]
        print(f"  {first_line}...")

        try:
            query_job = client.query(statement)
            query_job.result()  # Wait for completion
            print(f"  ✓ Statement {i} executed successfully")
            success_count += 1
        except Exception as e:
            print(f"  ✗ Statement {i} failed: {e}")
            error_count += 1
            # Continue with other statements even if one fails

    print("\n" + "=" * 70)
    print("Deployment Summary")
    print("=" * 70)
    print(f"Successful: {success_count}")
    print(f"Failed: {error_count}")
    print("=" * 70)

    # Verify the schema
    print("\nVerifying schema deployment...")
    dataset_ref = f"{args.project_id}.{args.dataset}"
    table_ref = f"{dataset_ref}.{args.table}"

    # Ensure dataset exists
    try:
        dataset = client.get_dataset(dataset_ref)
        print(f"✓ Dataset '{args.dataset}' exists")
        print(f"  Location: {dataset.location}")
        print(f"  Description: {dataset.description}")
    except Exception as e:
        print(f"⚠ Dataset '{args.dataset}' not found, attempting to create...")
        # Try to find and re-execute the CREATE SCHEMA statement
        for statement in statements:
            if "CREATE SCHEMA" in statement.upper():
                try:
                    query_job = client.query(statement)
                    query_job.result()
                    print(f"✓ Dataset '{args.dataset}' created successfully")
                    break
                except Exception as create_err:
                    print(f"✗ Failed to create dataset: {create_err}")
                    error_count += 1

    # Ensure table exists
    table_exists = False
    try:
        table = client.get_table(table_ref)
        print(f"✓ Table '{args.table}' exists")
        print(f"  Rows: {table.num_rows}")
        print(f"  Fields: {len(table.schema)}")
        table_exists = True
    except Exception as e:
        print(f"⚠ Table '{args.table}' not found, attempting to create...")
        # Try to find and re-execute the CREATE TABLE statement
        for statement in statements:
            if "CREATE TABLE" in statement.upper() and args.table in statement:
                try:
                    query_job = client.query(statement)
                    query_job.result()
                    print(f"✓ Table '{args.table}' created successfully")
                    table_exists = True
                    # Verify the table was created
                    table = client.get_table(table_ref)
                    print(f"  Rows: {table.num_rows}")
                    print(f"  Fields: {len(table.schema)}")
                    break
                except Exception as create_err:
                    print(f"✗ Failed to create table: {create_err}")
                    error_count += 1

    # Check if view exists (optional)
    if table_exists:
        view_ref = f"{dataset_ref}.active_queries"
        try:
            view = client.get_table(view_ref)
            print(f"✓ View 'active_queries' exists")
        except Exception:
            print("⚠ View 'active_queries' not found, attempting to create...")
            # Try to find and re-execute the CREATE VIEW statement
            for statement in statements:
                if "CREATE OR REPLACE VIEW" in statement.upper() and "active_queries" in statement:
                    try:
                        query_job = client.query(statement)
                        query_job.result()
                        print(f"✓ View 'active_queries' created successfully")
                        break
                    except Exception as view_err:
                        print(f"⚠ Failed to create view: {view_err}")

    print("\n" + "=" * 70)
    if error_count == 0:
        print("Schema deployed successfully!")
    else:
        print(f"Schema deployed with {error_count} errors")
    print("=" * 70)

    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
