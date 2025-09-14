import logging
import json
import os

from dotenv import load_dotenv
from google.cloud import logging as google_logging

load_dotenv()


def setup_llm_logger():
    """Sets up a logger to log LLM calls to a file or Google Cloud Logging."""
    if os.getenv("LOG_TO_GCP", "false").lower() == "true":
        logging_client = google_logging.Client()
        logger = logging_client.logger("llm_usage")
    else:
        logger = logging.getLogger('llm_usage')
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler('llm_usage.log')
        formatter = logging.Formatter('%(asctime)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def log_llm_call(logger, agent_name, user_email, usage_metadata, labels=None):
    """Logs the details of an LLM call."""

    # Add a hardcoded label for the application
    if labels is None:
        labels = {}
    labels["app"] = "adk"

    log_entry = {
        'agent_name': agent_name,
        'user_email': user_email,
        'usage_metadata': {
            'traffic_type': usage_metadata.traffic_type,
            'cached_content_token_count': usage_metadata.cached_content_token_count,
            'candidates_token_count': usage_metadata.candidates_token_count,
            'prompt_token_count': usage_metadata.prompt_token_count,
            'thoughts_token_count': usage_metadata.thoughts_token_count,
            'tool_use_prompt_token_count': usage_metadata.tool_use_prompt_token_count,
            'total_token_count': usage_metadata.total_token_count,
        },
        'labels': labels
    }

    if isinstance(logger, google_logging.Logger):
        logger.log_struct(log_entry, labels=labels)
    else:
        logger.info(json.dumps(log_entry))
