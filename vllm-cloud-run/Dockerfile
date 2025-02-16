FROM vllm/vllm-openai:latest

ENV HF_HOME=$MODEL_DOWNLOAD_DIR
ENV HF_HUB_OFFLINE=1

ENTRYPOINT python3 -m vllm.entrypoints.openai.api_server \
  --port ${PORT:-8080} \
  --model $MODEL_NAME \
  --trust-remote-code \
  --gpu-memory-utilization ${GPU_MEMORY_UTILIZATION:-0.95} \
  --max-model-len ${MAX_MODEL_LEN:-8192} \
  --max-num-batched-tokens ${MAX_NUM_BATCHED_TOKENS:-16384}