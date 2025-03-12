# Deploy DeepSeek R1 on Cloud Run with Hugging Face TGI

Guide followed: [R1 on Cloud Run](https://huggingface.co/docs/google-cloud/examples/cloud-run-tgi-deployment)

## Learnings
- Less steps to deploy
- The default option is to download the model from hugging face at runtime, this would only work if you connect to Cloud Nat, or it's too slow and times out.
- 4 cores and 16GB of RAM doesn't work, and it doesn't explain why in the deployment, use 8 core and 32GB minimum.
- As expected download is required on scaling up, and it takes around ~60 to spin-up the instance.
- Token generation is around ~16/s, reduced to ~7/s if max token is increased to 2048 with 60+ concurrent requests.
- Making 120 concurrent requests, even if there are 2 GPUs, it crashes many requests
- Inference is very efficient, 512 token performed twice as good as vllm. 
- Very reliable, 1024 output token crashes on vllm with even 5 concurrent requests, but no issues with tgi even on 60 concurrent requests, both per GPU.
- However, significant slow down (about half) when, increasing token size to 1024 with maxed out concurrency per instance (60) 

## Inference Performance
- The `max_tokens` parameter in the request affect performance and concurrency significantly. 
  - concurrency: 30, max_tokens: 128 -> Autoscalling triggered: no, Request latency: p99: ~9 seconds, Token Gen Throughput: ~14 / second, errors: no error 
  - concurrency: 30, max_tokens: 256 -> Autoscalling triggered: no, Request latency p99: ~17 seconds, Token Gen Throughput: ~15 / second, errors: no error 
  - concurrency: 30, max_tokens: 512 -> Autoscalling triggered: no, Request latency p99: ~35 seconds, Token Gen Throughput: ~15 / second, errors: no error 
  - concurrency: 30, max_tokens: 1024 -> Autoscalling triggered: no, Request latency p99: ~74 seconds, Token Gen Throughput: ~14 / second, errors: no errors
  - concurrency: 30, max_tokens: 2048 -> Autoscalling triggered: no, Request latency p99: ~150 seconds, Token Gen Throughput: ~14 / second, errors: no errors
  - concurrency: 60, max_tokens: 128 -> Autoscalling triggered: no, Request latency p99: ~10 seconds, Token Gen Throughput: ~13 / second, errors: no errors
  - concurrency: 60, max_tokens: 256 -> Autoscalling triggered: no, Request latency p99: ~20 seconds, Token Gen Throughput: ~13 / second, errors: no errors
  - concurrency: 60, max_tokens: 512 -> Autoscalling triggered: no, Request latency p99: ~42 seconds, Token Gen Throughput: ~12 / second, errors: no errors
  - concurrency: 60, max_tokens: 1024 -> Autoscalling triggered: no, Request latency p99: ~85 seconds, Token Gen Throughput: ~12 / second, errors: no errors
  - (triggered scale up then dropped immediately, had some errors, significant reduction of performance) concurrency: 60, max_tokens: 2048 -> Autoscalling triggered: no, Request latency p99: ~300 seconds, Token Gen Throughput: ~7 / second, errors: 5 errors


## Setup

Env vars
```
export REPOSITORY_NAME=practical-gcp
export REPOSITORY_REGOIN=europe-west4
export PROJECT_ID=rocketech-de-pgcp-sandbox
export LOCATION=europe-west4 # or any location where Cloud Run offers GPUs: https://cloud.google.com/run/docs/locations#gpu
export CONTAINER_URI=us-docker.pkg.dev/deeplearning-platform-release/gcr.io/huggingface-text-generation-inference-cu121.2-2.ubuntu2204.py310
export SERVICE_NAME=tgi-cloud-run
export VPC=private
export SUBNET=cloud-run-llm
export LLM_MODEL=deepseek-ai/DeepSeek-R1-Distill-Qwen-7B
```

Push the container into your own Artifact Registry
```
gcloud artifacts repositories create $REPOSITORY_NAME \
    --repository-format=docker \
    --location=$REPOSITORY_REGOIN

gcloud auth configure-docker $REPOSITORY_REGOIN-docker.pkg.dev
docker pull us-docker.pkg.dev/deeplearning-platform-release/gcr.io/huggingface-text-generation-inference-cu121.2-2.ubuntu2204.py310
docker tag us-docker.pkg.dev/deeplearning-platform-release/gcr.io/huggingface-text-generation-inference-cu121.2-2.ubuntu2204.py310 \
    $REPOSITORY_REGOIN-docker.pkg.dev/$PROJECT_ID/$REPOSITORY_NAME/huggingface-text-generation-inference:latest
docker push $REPOSITORY_REGOIN-docker.pkg.dev/$PROJECT_ID/$REPOSITORY_NAME/huggingface-text-generation-inference:latest
```

## Deploy to Cloud Run
> Please note, this way will require the deployed container to download the model from HuggingFace via the internet. 
> Also, if you are accessing private or models requires consent, you need to use a token. Token can be generated here, and 
> you also need to set an environment variable --set-env-vars=HF_TOKEN="your token"

```
gcloud beta run deploy $SERVICE_NAME \
    --image=$CONTAINER_URI \
    --set-env-vars=HF_HUB_ENABLE_HF_TRANSFER=1 \
    --args="--model-id=$LLM_MODEL, --max-concurrent-requests=64" \
    --port=8080 \
    --cpu=8 \
    --memory=32Gi \
    --no-cpu-throttling \
    --gpu=1 \
    --gpu-type=nvidia-l4 \
    --max-instances=3 \
    --concurrency=64 \
    --region=$LOCATION \
    --network=$VPC \
    --subnet=$SUBNET \
    --vpc-egress=all-traffic \
    --no-allow-unauthenticated
```