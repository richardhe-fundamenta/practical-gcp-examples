# Building the Admin UI Image

## Quick Start

```bash
./scripts/build_admin_ui.sh
```

## Custom Configuration

```bash
# Custom tag
IMAGE_TAG=v1.0.0 ./scripts/build_admin_ui.sh

# Different region
REGION=us-west1 ./scripts/build_admin_ui.sh

# Custom repository
REPOSITORY=my-repo ./scripts/build_admin_ui.sh
```

## Manual Build

```bash
gcloud builds submit --config=admin_ui/cloudbuild.yaml .
```

## Local Development

```bash
docker build -f admin_ui/Dockerfile -t admin-ui:dev .
docker run -p 8080:8080 --env-file .env admin-ui:dev
```
