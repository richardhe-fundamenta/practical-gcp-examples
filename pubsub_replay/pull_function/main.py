import json
import logging
import os

from google.cloud import pubsub_v1
from google.api_core import retry

BATCH_SIZE = 100
MAX_MESSAGES = 1000  # Maximum messages per function invocation
MAX_EMPTY_RESPONSES = 2  # Number of empty pulls before stopping

retry_config = retry.Retry(
    initial=1.0,  # Initial delay in seconds
    maximum=60.0,  # Maximum delay between retries
    multiplier=2.0,  # Multiplier applied to delay each retry
    deadline=30.0,  # Total time limit for all retries
    predicate=retry.if_transient_error  # Function to determine if error is retryable
)

logging.basicConfig(level=logging.INFO)


def process_messages(event, context):
    project_id = os.getenv('PROJECT_ID')
    subscription_id = os.getenv('SUBSCRIPTION_ID')

    if not project_id or not subscription_id:
        raise ValueError("Required environment variables PROJECT_ID and SUBSCRIPTION_ID must be set")

    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(project_id, subscription_id)

    logging.info(f"Starting batch processing for subscription: {subscription_path}")

    processed_count = 0
    empty_responses = 0  # Track consecutive empty pulls

    while processed_count < MAX_MESSAGES:
        try:
            # Pull batch of messages
            response = subscriber.pull(
                request={
                    "subscription": subscription_path,
                    "max_messages": BATCH_SIZE,
                },
                retry=retry_config
            )

            # If no messages, increment empty counter
            if not response.received_messages:
                empty_responses += 1
                logging.info(f"No messages received. Empty pull count: {empty_responses}")

                if empty_responses >= MAX_EMPTY_RESPONSES:
                    logging.info(f"No more messages to process after {processed_count} messages. Stopping.")
                    break
                continue

            # Reset empty counter if we got messages
            empty_responses = 0

            # Process the batch
            ack_ids = []
            messages_in_batch = len(response.received_messages)
            logging.info(f"Processing batch of {messages_in_batch} messages")

            for received_message in response.received_messages:
                try:
                    message = received_message.message
                    message_data = json.loads(message.data.decode("utf-8"))

                    # Log message details
                    logging.info(f"Processing message {message.message_id}")
                    logging.info(f"Transaction state: {message_data.get('state')}")

                    # Add your message processing logic here
                    # ...

                    ack_ids.append(received_message.ack_id)
                    processed_count += 1

                except Exception as e:
                    logging.error(f"Error processing message {message.message_id}: {e}")
                    # Consider adding to a dead-letter queue here

            # Acknowledge the processed messages
            if ack_ids:
                subscriber.acknowledge(
                    request={
                        "subscription": subscription_path,
                        "ack_ids": ack_ids,
                    }
                )
                logging.info(f"Acknowledged {len(ack_ids)} messages")

        except Exception as e:
            logging.error(f"Error in batch processing: {e}")
            break

    subscriber.close()
    logging.info(f"Function complete. Processed {processed_count} total messages")
    return f"Processed {processed_count} messages"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    process_messages(None, None)
