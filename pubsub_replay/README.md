# PubSub Replay Demo

[![Subscribe on YouTube](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fapi.socialcounts.org%2Fyoutube-live-subscriber-count%2FUC3XbEkSbPOzHvqNBrjNIu7A&query=%24.counters.api.subscriberCount&label=Subscribe&suffix=%20subscribers&color=FF0000&logo=youtube&logoColor=white&style=for-the-badge)](https://www.youtube.com/@practicalgcp2780?sub_confirmation=1)
[![Videos](https://img.shields.io/badge/90%2B_videos-Watch_all-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://www.youtube.com/playlist?list=UU3XbEkSbPOzHvqNBrjNIu7A)

_Code from the [PracticalGCP](https://www.youtube.com/@practicalgcp2780) YouTube channel._


## Create Infrastructure

```
terraform init
terraform plan -var="project_id=YOUR_PROJECT_ID"
terraform apply -var="project_id=YOUR_PROJECT_ID"
```

## Produce Examples Transactions

```
python ./pull_function/publish_example_messages.py \
    --project-id=YOUR_PROJECT_ID \
    --topic-id=transaction-state-events \
    --input-file=./pull_function/fake_transactions.jsonl
```

## Create Snapshot

> This is typically combined with deployment for disaster recovery

```
gcloud pubsub snapshots create deployment-$(date +%Y%m%d-%H%M%S) --subscription=transaction-state-events-pull
```

## Seek Snapshot - Replay

> This will replay all messages from the snapshot, snapshot will be deleted automatically after 7 days of retention

```
gcloud pubsub snapshots list
gcloud pubsub subscriptions seek transaction-state-events-pull --snapshot=SNAPSHOT_NAME
```