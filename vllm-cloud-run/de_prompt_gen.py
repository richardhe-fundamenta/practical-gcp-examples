import random

# List of question templates
question_templates = [
    "How would you design an Airflow DAG to handle a daily ETL pipeline that processes data from {source} to {destination}?",
    "Write an Airflow task to validate the schema of a {file_type} file stored in {storage} before processing.",
    "How would you optimize an Airflow DAG that is experiencing performance bottlenecks due to {issue}?",
    "Write a Python function to dynamically generate Airflow tasks based on a list of {input_parameter}.",
    "How would you handle task dependencies in an Airflow DAG where {task_A} must run only if {task_B} succeeds?",
    "Write an Airflow sensor to wait for a file named {file_name} to appear in {storage} before proceeding.",
    "How would you configure retries and retry delays for an Airflow task that interacts with {external_service}?",
    "Write a Cloud Composer DAG to orchestrate a data pipeline that processes data from {source} and loads it into {destination}.",
    "How would you monitor and alert for failed tasks in an Airflow DAG running on Cloud Composer?",
    "Write an Airflow task to backfill data from {start_date} to {end_date} for a specific {dataset}.",
    "How would you secure sensitive information (e.g., API keys) in an Airflow DAG running on Cloud Composer?",
    "Write an Airflow DAG to handle a scenario where {task} fails and needs to trigger a rollback process.",
    "How would you scale an Airflow DAG to process {large_dataset} efficiently in Cloud Composer?",
    "Write a Python script to automate the deployment of an Airflow DAG to a Cloud Composer environment.",
    "How would you debug an Airflow DAG that is stuck in a {state} state in Cloud Composer?",
]

# Placeholder values for dynamic question generation
placeholders = {
    "source": ["BigQuery", "Google Cloud Storage", "Pub/Sub", "MySQL", "PostgreSQL"],
    "destination": ["BigQuery", "Google Cloud Storage", "Dataflow", "Snowflake", "Redshift"],
    "file_type": ["CSV", "JSON", "Parquet", "Avro"],
    "storage": ["Google Cloud Storage", "AWS S3", "Azure Blob Storage"],
    "issue": ["high task concurrency", "long-running tasks", "resource contention"],
    "input_parameter": ["table names", "file paths", "dates"],
    "task_A": ["data extraction", "data transformation", "data validation"],
    "task_B": ["data loading", "data cleaning", "data aggregation"],
    "external_service": ["BigQuery", "Cloud SQL", "REST API"],
    "file_name": ["data.csv", "input.json", "output.parquet"],
    "start_date": ["2023-01-01", "2022-12-01", "2023-03-15"],
    "end_date": ["2023-01-31", "2022-12-31", "2023-03-31"],
    "dataset": ["sales", "user_activity", "inventory"],
    "task": ["data extraction", "data transformation", "data loading"],
    "large_dataset": ["1TB of logs", "10 million rows", "100GB of images"],
    "state": ["running", "queued", "failed"],
}


def generate_question(template, placeholders):
    """Generate a question by replacing placeholders with random values."""
    for key, values in placeholders.items():
        if f"{{{key}}}" in template:
            template = template.replace(f"{{{key}}}", random.choice(values))
    return template


def generate(num_prompts):
    # Generate the specified number of unique questions

    for _ in range(num_prompts):
        template = random.choice(question_templates)
        yield generate_question(template, placeholders)
