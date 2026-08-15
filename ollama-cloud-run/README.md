# Run Ollama with Deepseek on Cloud Run

[![Subscribe on YouTube](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fapi.socialcounts.org%2Fyoutube-live-subscriber-count%2FUC3XbEkSbPOzHvqNBrjNIu7A&query=%24.counters.api.subscriberCount&label=Subscribe&suffix=%20subscribers&color=FF0000&logo=youtube&logoColor=white&style=for-the-badge)](https://www.youtube.com/@practicalgcp2780?sub_confirmation=1)
[![Videos](https://img.shields.io/badge/90%2B_videos-Watch_all-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://www.youtube.com/playlist?list=UU3XbEkSbPOzHvqNBrjNIu7A)

_Code from the [PracticalGCP](https://www.youtube.com/@practicalgcp2780) YouTube channel._

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
