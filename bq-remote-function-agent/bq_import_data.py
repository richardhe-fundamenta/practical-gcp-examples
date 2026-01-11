import json
import os
import sys
import copy

try:
    from google.cloud import bigquery
except ImportError:
    print("Error: google-cloud-bigquery not found. Please install it with: pip install google-cloud-bigquery")
    sys.exit(1)

# Configuration
PROJECT_ID = "rocketech-de-pgcp-sandbox"
DATASET_ID = "bigquery_remotefunction_examples"
TABLE_ID = "customer_scenarios"
JSON_FILE_PATH = "customer-advisor/data/customer_scenarios.json"
TARGET_RECORDS = 10000

def import_data():
    """
    Imports customer scenarios from local JSON file into a BigQuery table.
    Generates 10k records by using the 10 scenarios as templates.
    """
    # Initialize BigQuery Client
    client = bigquery.Client(project=PROJECT_ID)
    
    # Resolve absolute path to the data file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_file_path = os.path.join(script_dir, JSON_FILE_PATH)
    
    if not os.path.exists(data_file_path):
        print(f"Error: Data file not found at {data_file_path}")
        return

    print(f"Reading templates from {data_file_path}...")
    with open(data_file_path, 'r') as f:
        data = json.load(f)
    
    # Extract template records from the "calls" array
    templates = [call[0] for call in data.get('calls', [])]
    
    if not templates:
        print("No records found in 'calls' array.")
        return

    print(f"Generating {TARGET_RECORDS} customer records from {len(templates)} templates...")
    
    all_records = []
    num_templates = len(templates)
    
    for i in range(TARGET_RECORDS):
        # Pick a template (cycling)
        template = templates[i % num_templates]
        
        # Deep copy to avoid modifying templates
        record = copy.deepcopy(template)
        
        # Make customer_id and name unique
        base_id = record.get("customer_id", "C000")
        base_name = record.get("name", "User")
        
        record["customer_id"] = f"{base_id}_{i:05d}"
        record["name"] = f"{base_name} #{i:05d}"
        
        all_records.append(record)

    print(f"Generated {len(all_records)} records.")

    # Target table reference
    dataset_ref = bigquery.DatasetReference(PROJECT_ID, DATASET_ID)
    table_ref = dataset_ref.table(TABLE_ID)
    
    # Configure the load job
    job_config = bigquery.LoadJobConfig(
        autodetect=True,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    
    print(f"Loading data into {PROJECT_ID}.{DATASET_ID}.{TABLE_ID}...")
    
    # For 10k records, we might want to batch, but load_table_from_json should 
    # handle 10k small JSON objects without issues in memory.
    try:
        job = client.load_table_from_json(
            all_records,
            table_ref,
            job_config=job_config
        )
        
        print(f"Started job {job.job_id}. Waiting for completion...")
        job.result()  # Wait for completion
        
        print(f"✅ Successfully loaded {len(all_records)} rows into {TABLE_ID}.")
        
    except Exception as e:
        print(f"❌ Error loading data: {e}")

if __name__ == "__main__":
    import_data()
