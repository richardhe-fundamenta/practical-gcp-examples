# Deploy DeepSeek R1 on Cloud Run with VLLM

Guide followed: [R1 on Cloud Run](https://medium.com/google-cloud/scale-to-zero-llm-inference-with-vllm-cloud-run-and-cloud-storage-fuse-42c7e62f6ec6)

## A few things to note on the guide (issues I discovered)
- Depending on the region you use, it [may not support](https://cloud.google.com/build/docs/locations#restricted_regions_for_some_projects) Cloud Build in that region. 
- The service account created need write access to the cloud storage bucket. 
- You'll need a bigger Cloud Build machine (I used  e2-highcpu-32) to build the container, or it gets stuck forever. 
- Cloud run container start-up time is very long (> 3 minutes), this is mostly time spent on "loading safetensors". 
- The mount cloud storage bucket is extremely slow (failed deployment after 10 minutes, never had a successful deployment), if you don't route traffic through VPC.


## Inference Performance 
- The `max_tokens` parameter in the request affect performance and concurrency significantly. Avg token generation is ~17/s
  - concurrency: 30, max_tokens: 128 -> Autoscalling triggered: no, Request latency: p99: ~16.5 seconds, Token Gen Throughput: ~22 / second, errors: no error 
  - concurrency: 30, max_tokens: 256 -> Autoscalling triggered: no, Request latency p99: ~33 seconds, Token Gen Throughput: ~15 / second, errors: no error 
  - concurrency: 30, max_tokens: 512 -> Autoscalling triggered: yes, Request latency p99: ~65 seconds, Token Gen Throughput: ~15 / second, errors: no error 
  - concurrency: 30, max_tokens: 1024 -> Autoscalling triggered: no, Request latency p99: N/A seconds, Token Gen Throughput: ~x / second, errors: aborted most requests
  - concurrency: 5, max_tokens: 1024 -> Autoscalling triggered: no, Request latency p99: N/A seconds, Token Gen Throughput: ~x / second, errors: aborted most requests

## Other Issues I cannot resolve
- When setting output token beyond 1024, it started retuning 504 errors, there's not much in the logs and MAX_MODEL_LENGTH is set to 100000, so it's unclear why requests fail


## Setup

Environment Variables
```
SERVICE_ACCOUNT=vllm-cloud-run
REGION=europe-west4
LABELS=purpose=rnd,owner=rh
DOCKER_REPO_NAME=practical-gcp
LLM_MODEL=deepseek-ai/DeepSeek-R1-Distill-Qwen-7B
PROJECT_ID=rocketech-de-pgcp-sandbox
MODELS_BUCKET_NAME=rocketech-de-pgcp-sandbox-llm-demo
RUN_NAME=vllm-r1-7b
VPC=private
SUBNET=cloud-run-llm
MAX_MODEL_LEN=100000
```

Everything else in between are skipped, see the instructions from the guide. 

Deploy
```
gcloud beta run deploy $RUN_NAME \
--project $PROJECT_ID \
--image ${REGION}-docker.pkg.dev/${PROJECT_ID}/${DOCKER_REPO_NAME}/vllm \
--execution-environment gen2 \
--cpu 8 \
--memory 32Gi \
--gpu 1 --gpu-type=nvidia-l4 \
--region $REGION \
--service-account $SERVICE_ACCOUNT@$PROJECT_ID.iam.gserviceaccount.com \
--no-allow-unauthenticated \
--concurrency 20 \
--min 0 \
--max-instances 3 \
--no-cpu-throttling \
--add-volume=name=vllm_mount,type=cloud-storage,bucket=$MODELS_BUCKET_NAME \
--add-volume-mount volume=vllm_mount,mount-path=/mnt/hf_cache \
--set-env-vars=HF_HOME=/mnt/hf_cache,MODEL_NAME=$LLM_MODEL \
--labels=$LABELS \
--network=$VPC \
--subnet=$SUBNET \
--vpc-egress=all-traffic \
--timeout=60
```

Proxy
```
gcloud run services proxy $RUN_NAME --region $REGION --project $PROJECT_ID
```

Test
```
curl -X POST http://localhost:8080/v1/completions \
-H "Content-Type: application/json" \
-d '{
  "model": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
  "prompt": "Google Cloud Run is a",
  "max_tokens": 128,
  "temperature": 0.90
}'
```


