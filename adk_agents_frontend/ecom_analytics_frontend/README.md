# The Ecom Analytics Agent Frontend
Examples on how to integrate a cloud run frontend with a lightweight backend to communicate with Agent Engine

## Env Vars
```
export ENGINE_ID=6495070271970476032
export GOOGLE_CLOUD_PROJECT=rocketech-de-pgcp-sandbox
export GOOGLE_GENAI_USE_VERTEXAI=True
export PROJECT_ID=rocketech-de-pgcp-sandbox
export GOOGLE_CLOUD_LOCATION=europe-west4
export CLOUDRUN_SA=cloudrun-ecom-analytics-app
export REPO=practical-gcp
```

## How to run locally
```
uv sync
uv run uvicorn src.main:app --reload
```

## Permissions
> Create cloud run service account
```
gcloud iam service-accounts create ${CLOUDRUN_SA} \
    --display-name="Cloud Run E-commerce Analytics App SA" \
    --description="Service account for the Cloud Run analytics application."
```

> Grand permission
```
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${CLOUDRUN_SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user" \
    --condition=None
```

## Deploy to Cloud Run
```
gcloud builds submit --config cloudbuild.yaml \
 --substitutions=_PROJECT_ID="${PROJECT_ID}",_REPO_NAME="${REPO}",_SERVICE_NAME="ecom-analytics",_LOCATION="${GOOGLE_CLOUD_LOCATION},_SERVICE_ACCOUNT=${CLOUDRUN_SA}@${PROJECT_ID}.iam.gserviceaccount.com,_ENGINE_ID=${ENGINE_ID}" .
```


## Resources
- IAP Auth examples: https://github.com/googlecodelabs/user-authentication-with-iap
- Enable IAP directly on Cloud Run: https://cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run
- The simplest way to enable IAP on Cloud Run: https://youtu.be/YLz3Xtf8LTc?si=XqeB5RyT2jW_AtmO
