import pandas as pd
import random
import uuid
from datetime import date
import math
import os

from google.cloud import bigquery
from google.cloud.exceptions import NotFound # Import NotFound exception
from faker import Faker


project_id = os.environ.get('PROJECT_ID', 'rocketech-de-pgcp-sandbox')
location = os.environ.get('LOCATION', 'europe-west2')

# --- Configuration ---
NUM_ROWS = 5000
PERCENT_ISSUES = 0.08  # Target ~8% of rows with at least one issue
PROJECT_ID = project_id
DATASET_ID = "dataplex_dq_demo"
TABLE_ID = "customer_with_issues"
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


# --- Generate Base Data with Nested Address ---
print(f"\nGenerating {NUM_ROWS} rows of synthetic UK customer data with nested address...")
data = []
for i in range(NUM_ROWS):
    # Create the nested dictionary for address details
    address_details = {
        "street_address": fake.street_address(),
        "city": fake.city(),
        "county": fake.county(),
        "postcode": fake.postcode(),
        "country": "United Kingdom"
    }
    # Append the full record, including the nested address dict
    data.append({
        "id": str(uuid.uuid4()),
        "first_name": fake.first_name(),
        "last_name": fake.last_name(),
        "email": fake.email(),
        "phone_number": fake.phone_number(),
        "address": address_details, # Assign the nested dictionary here
        "birthdate": fake.date_of_birth(minimum_age=18, maximum_age=90),
        "gender": random.choice(['Male', 'Female', 'Other', None]),
    })
print(f"Base data generated for {len(data)} customers.")

# --- Introduce Data Quality Issues ---
print(f"Introducing data quality issues (target < {PERCENT_ISSUES*100:.1f}%)...")
num_rows_with_issues = int(NUM_ROWS * PERCENT_ISSUES)
indices_to_modify = random.sample(range(NUM_ROWS), num_rows_with_issues)

num_missing_email = num_rows_with_issues // 4
# Modify missing postcode logic for nested structure
num_missing_postcode_in_address = num_rows_with_issues // 4
num_duplicate_id_pairs = num_rows_with_issues // 8
num_duplicate_email_pairs = num_rows_with_issues // 8

issue_counter = 0
affected_rows_count = 0

# 1. Missing Emails (Top Level)
print(f" - Adding {num_missing_email} missing emails...")
for i in range(num_missing_email):
    if issue_counter < len(indices_to_modify):
        idx = indices_to_modify[issue_counter]
        data[idx]['email'] = None
        issue_counter += 1
        affected_rows_count += 1

# 2. Missing Postcodes (Inside Address Struct)
print(f" - Adding {num_missing_postcode_in_address} missing postcodes inside address struct...")
for i in range(num_missing_postcode_in_address):
    if issue_counter < len(indices_to_modify):
        idx = indices_to_modify[issue_counter]
        # Access the nested field to set it to None
        # Check if the address struct itself exists first (it should always in this script)
        if data[idx]['address'] is not None:
             data[idx]['address']['postcode'] = None
        issue_counter += 1
        affected_rows_count += 1 # Count this row as affected

# 3. Duplicate IDs (Top Level)
print(f" - Creating {num_duplicate_id_pairs} duplicate ID pairs...")
potential_dup_indices = indices_to_modify[issue_counter:]
random.shuffle(potential_dup_indices)
ids_made_duplicate = set()
for i in range(num_duplicate_id_pairs):
    if len(potential_dup_indices) >= 2:
        idx_target = potential_dup_indices.pop()
        idx_source = potential_dup_indices.pop()
        if data[idx_source]['id'] not in ids_made_duplicate:
            data[idx_target]['id'] = data[idx_source]['id']
            ids_made_duplicate.add(data[idx_source]['id'])
            affected_rows_count += 2
            issue_counter += 2
        else:
             potential_dup_indices.append(idx_target)
             potential_dup_indices.append(idx_source)

# 4. Duplicate Emails (Top Level)
print(f" - Creating {num_duplicate_email_pairs} duplicate email pairs...")
random.shuffle(potential_dup_indices)
emails_made_duplicate = set()
for i in range(num_duplicate_email_pairs):
    if len(potential_dup_indices) >= 2:
        idx_target = potential_dup_indices.pop()
        idx_source = potential_dup_indices.pop()
        source_email = data[idx_source]['email']
        if source_email is not None and source_email not in emails_made_duplicate:
            data[idx_target]['email'] = source_email
            emails_made_duplicate.add(source_email)
            affected_rows_count += 2
            issue_counter += 2
        else:
             potential_dup_indices.append(idx_target)
             potential_dup_indices.append(idx_source)

print(f"Finished introducing issues. Approximately {affected_rows_count} distinct rows affected by one or more issues.")

# --- Create Pandas DataFrame ---
print("\nCreating Pandas DataFrame...")
df = pd.DataFrame(data)
# Birthdate conversion remains the same
df['birthdate'] = pd.to_datetime(df['birthdate'], errors='coerce').dt.date
print("DataFrame created.")
print("Sample data showing nested structure (first 5 rows):")
# Displaying the head might truncate the nested dict, but shows the structure
print(df.head())
print("\nData Info (note 'address' column type is object):")
df.info()

# --- Define BigQuery Schema with Address STRUCT ---
print("\nDefining BigQuery schema with nested address struct...")
schema = [
    bigquery.SchemaField("id", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("first_name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("last_name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("email", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("phone_number", "STRING", mode="NULLABLE"),
    # Define the address field as STRUCT/RECORD
    bigquery.SchemaField("address", "STRUCT", mode="NULLABLE", # Or "RECORD"
        fields=[
            bigquery.SchemaField("street_address", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("city", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("county", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("postcode", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("country", "STRING", mode="NULLABLE"),
        ]
    ),
    bigquery.SchemaField("birthdate", "DATE", mode="NULLABLE"),
    bigquery.SchemaField("gender", "STRING", mode="NULLABLE"),
]
print("Schema defined.")

# --- Create BigQuery Table ---
print(f"\nAttempting to create BigQuery table: {TABLE_REF_FULL}")
table = bigquery.Table(TABLE_REF_FULL, schema=schema)
try:
    client.create_table(table, exists_ok=True)
    print(f"Table {TABLE_REF_FULL} created or already exists.")
except Exception as e:
    print(f"Error creating BigQuery table: {e}")
    print("Please check permissions (e.g., BigQuery Data Editor role).")
    exit()

# --- Load Data into BigQuery ---
print(f"Loading data into {TABLE_REF_FULL}...")
job_config = bigquery.LoadJobConfig(
    schema=schema, # Crucial to provide the schema with the STRUCT definition
    write_disposition="WRITE_TRUNCATE",
)
try:
    # The client library handles converting the column containing Python dicts
    # into the BigQuery STRUCT format based on the provided schema.
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

print("\nScript finished.")
