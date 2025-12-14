.PHONY: install dev deploy clean test lint

# Project configuration
PROJECT_ID ?= $(shell gcloud config get-value project)
REGION ?= us-central1
SERVICE_NAME = bigquery-data-insight-builder

install:
	@echo "Installing dependencies..."
	uv sync

dev:
	@echo "Starting development server..."
	uv run python -m uvicorn app.main:app --reload --port 8080

deploy-authenticated:
	@echo "Deploying to Cloud Run with authentication..."
	@if [ -z "$(PROJECT_ID)" ]; then \
		echo "Error: PROJECT_ID not set. Run 'gcloud config set project YOUR_PROJECT_ID'"; \
		exit 1; \
	fi
	gcloud run deploy $(SERVICE_NAME) \
		--source . \
		--region $(REGION) \
		--platform managed \
		--no-allow-unauthenticated \
		--service-account default \
		--memory 512Mi \
		--cpu 1 \
		--max-instances 10 \
		--project $(PROJECT_ID)
