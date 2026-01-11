import json
import os
import sys

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

def import_data():
    """
    Imports customer scenarios from local JSON file into a BigQuery table.
    The records are extracted from the 'calls' array in the JSON file.
    """
    # Initialize BigQuery Client
    client = bigquery.Client(project=PROJECT_ID)
    
    # Resolve absolute path to the data file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_file_path = os.path.join(script_dir, JSON_FILE_PATH)
    
    if not os.path.exists(data_file_path):
        print(f"Error: Data file not found at {data_file_path}")
        return

    print(f"Reading data from {data_file_path}...")
    with open(data_file_path, 'r') as f:
        data = json.load(f)
    
    # Extract records from the "calls" array (each call is a list of arguments [record])
    # We take the first argument of each row as our record object.
    records = [call[0] for call in data.get('calls', [])]
    
    if not records:
        print("No records found in 'calls' array.")
        return

    print(f"Extracted {len(records)} customer records.")

    # Target table reference
    dataset_ref = bigquery.DatasetReference(PROJECT_ID, DATASET_ID)
    table_ref = dataset_ref.table(TABLE_ID)
    
    # Configure the load job
    job_config = bigquery.LoadJobConfig(
        autodetect=True,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    
    print(f"Loading data into {PROJECT_ID}.{DATASET_ID}.{TABLE_ID}...")
    
    try:
        job = client.load_table_from_json(
            records,
            table_ref,
            job_config=job_config
        )
        
        print(f"Started job {job.job_id}. Waiting for completion...")
        job.result()  # Wait for completion
        
        print(f"✅ Successfully loaded {len(records)} rows into {TABLE_ID}.")
        
    except Exception as e:
        print(f"❌ Error loading data: {e}")

if __name__ == "__main__":
    import_data()
