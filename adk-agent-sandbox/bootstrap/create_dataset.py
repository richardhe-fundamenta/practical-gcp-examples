"""Bootstrap script: create the analyst_demo BigQuery dataset (US location).

Creates a small star-schema dataset with four related tables that support the
analyst agent's demo questions:
  - customers  (200 rows)  — customer_id, name, region, plan_tier, signup_date
  - products   ( 40 rows)  — product_id, product_name, category, unit_price
  - orders     (3000 rows) — order_id, customer_id, order_date, status
  - order_items(8000 rows) — order_item_id, order_id, product_id, quantity

Revenue is intentionally NOT stored in any table; the agent must compute it
via the join: SUM(oi.quantity * p.unit_price).

Example question the agent can answer:
  "Show me monthly revenue by region for completed orders over the last year."

Run with:
  uv run python bootstrap/create_dataset.py
"""

import os
from datetime import date, timedelta

import google.auth
import numpy as np
import pandas as pd
from google.cloud import bigquery
from google.cloud.bigquery import LoadJobConfig, SchemaField

DATASET_ID = "analyst_demo"
LOCATION = "US"
RANDOM_SEED = 42


def get_project() -> str:
    """Return project from env override or ADC."""
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if project:
        return project
    _, adc_project = google.auth.default()
    if not adc_project:
        raise RuntimeError(
            "Could not determine GCP project. "
            "Set GOOGLE_CLOUD_PROJECT or configure ADC."
        )
    return adc_project


def create_dataset(client: bigquery.Client, project: str) -> None:
    """Create dataset if it doesn't exist."""
    dataset_ref = bigquery.Dataset(f"{project}.{DATASET_ID}")
    dataset_ref.location = LOCATION
    client.create_dataset(dataset_ref, exists_ok=True)
    print(f"Dataset {project}.{DATASET_ID} ready (location={LOCATION}).")


def make_customers(rng: np.random.Generator, n: int = 200) -> pd.DataFrame:
    regions = ["NA", "EMEA", "APAC", "LATAM"]
    plan_tiers = ["Free", "Pro", "Enterprise"]
    # Weights skewed: more Free than Enterprise
    region_weights = [0.40, 0.30, 0.20, 0.10]
    tier_weights = [0.50, 0.35, 0.15]

    first_names = [
        "Alice", "Bob", "Carol", "David", "Eva", "Frank", "Grace", "Hank",
        "Isla", "Jack", "Karen", "Leo", "Maya", "Nate", "Olivia", "Paul",
        "Quinn", "Rachel", "Sam", "Tara",
    ]
    last_names = [
        "Smith", "Jones", "Williams", "Brown", "Davis", "Miller", "Wilson",
        "Moore", "Taylor", "Anderson", "Thomas", "Jackson", "White", "Harris",
        "Martin", "Thompson", "Garcia", "Martinez", "Robinson", "Clark",
    ]
    names = [
        f"{rng.choice(first_names)} {rng.choice(last_names)}"
        for _ in range(n)
    ]

    # signup_date spread over the 3 years prior to our order window
    base_date = date(2022, 1, 1)
    signup_offsets = rng.integers(0, 365 * 3, size=n)
    signup_dates = [base_date + timedelta(days=int(d)) for d in signup_offsets]

    return pd.DataFrame(
        {
            "customer_id": list(range(1, n + 1)),
            "name": names,
            "region": rng.choice(regions, size=n, p=region_weights),
            "plan_tier": rng.choice(plan_tiers, size=n, p=tier_weights),
            "signup_date": signup_dates,
        }
    )


def make_products(rng: np.random.Generator, n: int = 40) -> pd.DataFrame:
    categories = ["Analytics", "Storage", "Compute", "Security", "Networking"]
    adjectives = ["Pro", "Lite", "Enterprise", "Core", "Advanced", "Basic", "Plus"]
    nouns = ["Suite", "Platform", "Tool", "Engine", "Hub", "Cloud", "Pack"]

    product_names = []
    for i in range(n):
        cat = categories[i % len(categories)]
        adj = adjectives[i % len(adjectives)]
        noun = nouns[i % len(nouns)]
        product_names.append(f"{cat} {adj} {noun}")

    unit_prices = rng.uniform(5.0, 500.0, size=n).round(2)
    category_labels = [categories[i % len(categories)] for i in range(n)]

    return pd.DataFrame(
        {
            "product_id": list(range(1, n + 1)),
            "product_name": product_names,
            "category": category_labels,
            "unit_price": unit_prices,
        }
    )


def make_orders(
    rng: np.random.Generator,
    customer_ids: list,
    n: int = 3000,
) -> pd.DataFrame:
    statuses = ["completed", "cancelled", "refunded"]
    status_weights = [0.75, 0.15, 0.10]

    # order_date spans ~18 months ending today
    end_date = date.today()
    start_date = end_date - timedelta(days=548)  # ~18 months
    span_days = (end_date - start_date).days

    order_offsets = rng.integers(0, span_days, size=n)
    order_dates = [start_date + timedelta(days=int(d)) for d in order_offsets]

    return pd.DataFrame(
        {
            "order_id": list(range(1, n + 1)),
            "customer_id": rng.choice(customer_ids, size=n),
            "order_date": order_dates,
            "status": rng.choice(statuses, size=n, p=status_weights),
        }
    )


def make_order_items(
    rng: np.random.Generator,
    order_ids: list,
    product_ids: list,
    n: int = 8000,
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "order_item_id": list(range(1, n + 1)),
            "order_id": rng.choice(order_ids, size=n),
            "product_id": rng.choice(product_ids, size=n),
            "quantity": rng.integers(1, 11, size=n),  # 1–10 inclusive
        }
    )


def load_table(
    client: bigquery.Client,
    df: pd.DataFrame,
    table_id: str,
    schema: list[SchemaField],
) -> None:
    job_config = LoadJobConfig(
        schema=schema,
        write_disposition="WRITE_TRUNCATE",
    )
    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()  # wait for completion
    table = client.get_table(table_id)
    print(f"  Loaded {table.num_rows:,} rows into {table_id}")


def run_verification(client: bigquery.Client, project: str) -> None:
    """Run a join + aggregation + time-series query to prove the data works."""
    sql = f"""
    SELECT
        FORMAT_DATE('%Y-%m', o.order_date) AS month,
        c.region,
        ROUND(SUM(oi.quantity * p.unit_price), 2) AS revenue
    FROM `{project}.{DATASET_ID}.orders` o
    JOIN `{project}.{DATASET_ID}.customers` c USING (customer_id)
    JOIN `{project}.{DATASET_ID}.order_items` oi USING (order_id)
    JOIN `{project}.{DATASET_ID}.products` p USING (product_id)
    WHERE o.status = 'completed'
    GROUP BY month, region
    ORDER BY month, region
    """
    print("\nVerification query (monthly completed-order revenue by region):")
    print("-" * 70)
    rows = client.query(sql).result()
    rows_list = list(rows)
    for row in rows_list[:12]:
        print(f"  {row.month}  {row.region:<6}  ${row.revenue:>12,.2f}")
    if len(rows_list) > 12:
        print(f"  ... ({len(rows_list) - 12} more rows)")
    print(f"\nTotal rows returned: {len(rows_list)}")
    if len(rows_list) == 0:
        raise RuntimeError("Verification query returned 0 rows — something is wrong!")
    print("Verification PASSED.")


def main() -> None:
    project = get_project()
    print(f"Using GCP project: {project}")

    rng = np.random.default_rng(RANDOM_SEED)

    # Generate synthetic data
    print("\nGenerating synthetic data (seed=42)...")
    customers_df = make_customers(rng, n=200)
    products_df = make_products(rng, n=40)
    orders_df = make_orders(rng, customers_df["customer_id"].tolist(), n=3000)
    order_items_df = make_order_items(
        rng,
        orders_df["order_id"].tolist(),
        products_df["product_id"].tolist(),
        n=8000,
    )
    print(
        f"  customers: {len(customers_df)}, products: {len(products_df)}, "
        f"orders: {len(orders_df)}, order_items: {len(order_items_df)}"
    )

    client = bigquery.Client(project=project)

    # Create dataset (idempotent)
    create_dataset(client, project)

    # Load tables with explicit schemas
    print("\nLoading tables (WRITE_TRUNCATE — safe to re-run)...")

    load_table(
        client,
        customers_df,
        f"{project}.{DATASET_ID}.customers",
        schema=[
            SchemaField("customer_id", "INTEGER"),
            SchemaField("name", "STRING"),
            SchemaField("region", "STRING"),
            SchemaField("plan_tier", "STRING"),
            SchemaField("signup_date", "DATE"),
        ],
    )

    load_table(
        client,
        products_df,
        f"{project}.{DATASET_ID}.products",
        schema=[
            SchemaField("product_id", "INTEGER"),
            SchemaField("product_name", "STRING"),
            SchemaField("category", "STRING"),
            SchemaField("unit_price", "FLOAT"),
        ],
    )

    load_table(
        client,
        orders_df,
        f"{project}.{DATASET_ID}.orders",
        schema=[
            SchemaField("order_id", "INTEGER"),
            SchemaField("customer_id", "INTEGER"),
            SchemaField("order_date", "DATE"),
            SchemaField("status", "STRING"),
        ],
    )

    load_table(
        client,
        order_items_df,
        f"{project}.{DATASET_ID}.order_items",
        schema=[
            SchemaField("order_item_id", "INTEGER"),
            SchemaField("order_id", "INTEGER"),
            SchemaField("product_id", "INTEGER"),
            SchemaField("quantity", "INTEGER"),
        ],
    )

    # Verify the data via a join + aggregation query
    run_verification(client, project)

    # Print env values to configure
    print("\n" + "=" * 70)
    print("Set these environment variables (e.g. in .env):")
    print(f"  BQ_DATASET_ALLOWLIST=analyst_demo")
    print(f"  BQ_DATA_REGION=US")
    print(f"  GOOGLE_CLOUD_PROJECT={project}")
    print("=" * 70)


if __name__ == "__main__":
    main()
