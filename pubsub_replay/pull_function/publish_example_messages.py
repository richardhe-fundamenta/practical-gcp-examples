# publish_messages.py

from google.cloud import pubsub_v1
import json
import argparse
from pathlib import Path
import time


class PubSubPublisher:
    def __init__(self, project_id: str, topic_id: str):
        self.publisher = pubsub_v1.PublisherClient()
        self.topic_path = self.publisher.topic_path(project_id, topic_id)

    def publish_message(self, message: dict) -> str:
        data = json.dumps(message).encode("utf-8")
        future = self.publisher.publish(self.topic_path, data)
        message_id = future.result()
        return message_id


def load_messages(file_path: str) -> list:
    messages = []
    with open(file_path, 'r') as f:
        for line in f:
            if line.strip():  # Skip empty lines
                messages.append(json.loads(line))
    return messages


def main():
    parser = argparse.ArgumentParser(description='Publish messages to PubSub from a JSONL file')
    parser.add_argument('--project-id', required=True, help='GCP Project ID')
    parser.add_argument('--topic-id', required=True, help='PubSub Topic ID')
    parser.add_argument('--input-file', required=True, help='Path to JSONL file containing messages')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between messages in seconds (default: 1.0)')

    args = parser.parse_args()

    # Check if file exists
    if not Path(args.input_file).exists():
        print(f"Error: File {args.input_file} not found")
        return

    # Initialize publisher
    publisher = PubSubPublisher(args.project_id, args.topic_id)

    # Load and publish messages
    messages = load_messages(args.input_file)
    print(f"Loaded {len(messages)} messages from {args.input_file}")

    for i, message in enumerate(messages, 1):
        try:
            message_id = publisher.publish_message(message)
            print(f"Published message {i}/{len(messages)} - ID: {message_id}, State: {message.get('state')}")

            if i < len(messages):  # Don't delay after the last message
                time.sleep(args.delay)

        except Exception as e:
            print(f"Error publishing message {i}: {e}")


if __name__ == "__main__":
    main()