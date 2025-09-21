import os
import logging
import vertexai
import asyncio

from agent import root_agent
from vertexai import agent_engines
from google.cloud import storage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("adk_ecommerce_analytics_agent")
logger.setLevel(logging.INFO)


def try_create_staging_bucket(bucket_name, location):
    # Create the staging bucket if it doesn't exist
    storage_client = storage.Client(project=PROJECT_ID)
    bucket_name = bucket_name.replace("gs://", "")
    bucket = storage_client.bucket(bucket_name)
    if not bucket.exists():
        bucket.create(location=location)
        logger.info(f"Bucket {bucket_name} created.")


PROJECT_ID = os.environ.get("PROJECT_ID", "rocketech-de-pgcp-sandbox")
LOCATION = "europe-west4"
STAGING_BUCKET = f"gs://{PROJECT_ID}-agent-engine-staging"

try_create_staging_bucket(STAGING_BUCKET, LOCATION)

# Initialize the Vertex AI SDK
vertexai.init(
    project=PROJECT_ID,
    location=LOCATION,
    staging_bucket=STAGING_BUCKET,
)

# Wrap the agent in an AdkApp object
app = agent_engines.AdkApp(
    agent=root_agent,
    enable_tracing=True,
)


# Local testing before it's deployed
async def create_and_print_session():
    session = await app.async_create_session(user_id="u_123")
    print(session)


asyncio.run(create_and_print_session())

# Deploy to agent engine
remote_app = agent_engines.create(
    display_name=root_agent.name,
    description=root_agent.description,
    agent_engine=app,
    requirements=[
        "google-cloud-aiplatform[adk,agent_engines]",
        "google-cloud-geminidataanalytics",
        "google-generativeai",
        "pandas",
        "google-adk"
    ],
    extra_packages=["."]
)

logger.info(f"Deployment finished!")
logger.info(f"Resource Name: {remote_app.resource_name}")
