"""Pipeline to load slack into bigquery."""

from typing import List

import dlt
from pendulum import datetime, now
from slack import slack_source


def get_messages_and_replies_of_a_channel(channel_name: str) -> None:
    """Execute a pipeline that will load the messages and replies of a channel."""
    pipeline = dlt.pipeline(
        pipeline_name="slack", destination='bigquery', dataset_name="dlt_examples"
    )

    # Note: if you use the table_per_channel=True, the message-resource will be named after the
    # channel, so if you want the replies to a channel, e.g. "3-technical-help", you have to name
    # it like this:
    # resources = ["3-technical-help", "3-technical-help_replies"]
    source = slack_source(
        start_date=None, # or now().subtract(weeks=1)
        end_date=None,
        selected_channels=[channel_name],
        include_private_channels=False,
        replies=True,
    ).with_resources(channel_name, f"{channel_name}_replies")

    load_info = pipeline.run(
        source,
    )
    print(load_info)


if __name__ == "__main__":
    get_messages_and_replies_of_a_channel("gcp-news")
