import pandas as pd
import random
import uuid
from datetime import date
import os

from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from faker import Faker

project_id = os.environ.get('PROJECT_ID', 'rocketech-de-pgcp-sandbox')
location = os.environ.get('LOCATION', 'europe-west2')

# --- Configuration for Perfect Data ---
NUM_ROWS = 5000
PROJECT_ID = project_id
DATASET_ID = "dataplex_dq_demo"
TABLE_ID = "customer_perfect"
LOCATION = location

# Fully qualified IDs
DATASET_REF_FULL = f"{PROJECT_ID}.{DATASET_ID}"
TABLE_REF_FULL = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

# --- Initialize Faker and BigQuery Client ---
fake = Faker('en_GB')

try:
    client = bigquery.Client(project=PROJECT_ID)
    print(f"BigQuery client initialized for project '{PROJECT_ID}'.")
except Exception as e:
    print(f"Error initializing BigQuery client: {e}")
    print("Please ensure you have authenticated and the project ID is correct.")
    exit()

# --- Check and Create Dataset if it Doesn't Exist ---
print(f"\nChecking for dataset: {DATASET_REF_FULL} in location {LOCATION}...")
try:
    client.get_dataset(DATASET_REF_FULL)
    print(f"Dataset {DATASET_REF_FULL} already exists.")
except NotFound:
    print(f"Dataset {DATASET_REF_FULL} not found. Creating dataset...")
    try:
        dataset = bigquery.Dataset(DATASET_REF_FULL)
        dataset.location = LOCATION
        dataset = client.create_dataset(dataset, timeout=30, exists_ok=True)
        print(f"Created dataset {dataset.project}.{dataset.dataset_id} in location {dataset.location}")
    except Exception as e:
        print(f"Error creating dataset {DATASET_REF_FULL}: {e}")
        print("Please check permissions (e.g., BigQuery Admin role might be needed for dataset creation).")
        exit()
except Exception as e:
    print(f"An error occurred while checking for dataset {DATASET_REF_FULL}: {e}")
    exit()

# --- Generate Perfect Data with Nested Address ---
print(f"\nGenerating {NUM_ROWS} rows of perfect synthetic UK customer data with nested address...")
data = []
for i in range(NUM_ROWS):
    address_details = {
        "street_address": fake.street_address(),
        "city": fake.city(),
        "county": fake.county(),
        "postcode": fake.postcode(),
        "country": "United Kingdom"
    }
    data.append({
        "id": str(uuid.uuid4()),
        "first_name": fake.first_name(),
        "last_name": fake.last_name(),
        "email": fake.email(),
        "phone_number": fake.phone_number(),
        "address": address_details,
        "birthdate": fake.date_of_birth(minimum_age=18, maximum_age=90),
        "gender": random.choice(['Male', 'Female', 'Other']),  # Ensuring no None for gender
    })
print(f"Perfect data generated for {len(data)} customers.")

# --- Create Pandas DataFrame ---
print("\nCreating Pandas DataFrame...")
df = pd.DataFrame(data)
df['birthdate'] = pd.to_datetime(df['birthdate'], errors='coerce').dt.date
print("DataFrame created.")
print("Sample perfect data showing nested structure (first 5 rows):")
print(df.head())
print("\nData Info (note 'address' column type is object):")
df.info()

# --- Define BigQuery Schema with Address STRUCT ---
print("\nDefining BigQuery schema with nested address struct...")
schema = [
    bigquery.SchemaField("id", "STRING", mode="REQUIRED"),  # Ensuring ID is not NULL
    bigquery.SchemaField("first_name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("last_name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("email", "STRING", mode="REQUIRED"),  # Ensuring email is not NULL
    bigquery.SchemaField("phone_number", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("address", "STRUCT", mode="REQUIRED",  # Ensuring address struct is not NULL
                         fields=[
                             bigquery.SchemaField("street_address", "STRING", mode="REQUIRED"),
                             # Ensuring street address is not NULL
                             bigquery.SchemaField("city", "STRING", mode="REQUIRED"),  # Ensuring city is not NULL
                             bigquery.SchemaField("county", "STRING", mode="NULLABLE"),
                             bigquery.SchemaField("postcode", "STRING", mode="REQUIRED"),
                             # Ensuring postcode is not NULL
                             bigquery.SchemaField("country", "STRING", mode="REQUIRED"),  # Ensuring country is not NULL
                         ]
                         ),
    bigquery.SchemaField("birthdate", "DATE", mode="REQUIRED"),  # Ensuring birthdate is not NULL
    bigquery.SchemaField("gender", "STRING", mode="REQUIRED"),  # Ensuring gender is not NULL
]
print("Schema defined for perfect data.")

# --- Create BigQuery Table for Perfect Data ---
print(f"\nAttempting to create BigQuery table for perfect data: {TABLE_REF_FULL}")
table = bigquery.Table(TABLE_REF_FULL, schema=schema)
try:
    client.create_table(table, exists_ok=True)
    print(f"Table {TABLE_REF_FULL} created or already exists.")
except Exception as e:
    print(f"Error creating BigQuery table: {e}")
    print("Please check permissions (e.g., BigQuery Data Editor role).")
    exit()

# --- Load Perfect Data into BigQuery ---
print(f"Loading perfect data into {TABLE_REF_FULL}...")
job_config = bigquery.LoadJobConfig(
    schema=schema,
    write_disposition="WRITE_TRUNCATE",
)
try:
    job = client.load_table_from_dataframe(
        df, TABLE_REF_FULL, job_config=job_config
    )
    job.result()
    print(f"Load job {job.job_id} completed.")
    table = client.get_table(TABLE_REF_FULL)
    print(f"Loaded {table.num_rows} rows into {TABLE_REF_FULL}.")
except Exception as e:
    print(f"Error loading data into BigQuery: {e}")
    if hasattr(e, 'errors'):
        print("Detailed errors:", e.errors)

print("\nScript finished. Perfect data table created and loaded.")
