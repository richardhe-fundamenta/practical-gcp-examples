# Run Ollama with Deepseek on Cloud Run
Deploy Ollama with Deepseek R1
- Google cloud run model deployment doc: https://cloud.google.com/run/docs/tutorials/gpu-gemma2-with-ollama
- Ollama api doc: https://github.com/ollama/ollama/tree/main/docs

## Build

```
export PROJECT_ID=<PLACEHOLDER>
export REPO=<PLACEHOLDER>
export SA=<PLACEHOLDER>

gcloud builds submit \
--tag europe-west4-docker.pkg.dev/${PROJECT_ID}/${REPO}/ollama-deepseek-r1b \
   --machine-type e2-highcpu-32
```

## Deploy
```
gcloud beta run deploy ollama-deepseek-r1b \
  --image us-central1-docker.pkg.dev/${PROJECT_ID}/${REPO}/ollama-deepseek-r1b \
  --concurrency 4 \
  --cpu 4 \
  --set-env-vars OLLAMA_NUM_PARALLEL=4 \
  --gpu 1 \
  --gpu-type nvidia-l4 \
  --max-instances 7 \
  --memory 16Gi \
  --no-allow-unauthenticated \
  --no-cpu-throttling \
  --service-account ${SA} \
  --timeout=600
```

## Connect

```
gcloud run services proxy ollama-deepseek-r1b --port=9090
```

Then run
> Interactive CLI
```
OLLAMA_HOST=http://127.0.0.1:9090 \
ollama run deepseek-r1:7b
```

> API
```
curl http://localhost:9090/api/generate -d '{
  "model": "deepseek-r1:7b",
  "prompt": "Why is the sky blue?"
}'
```
