# PubSub Replay Demo

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
    --input-file=./pull_function/fake_transactions.jsonl \
    --delay=1.0
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