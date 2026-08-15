# Thin render-job image: the prebuilt heavy base (Dockerfile.base) + app source.
# Only `COPY deck` changes on a code edit, so this builds in ~1-2m instead of
# rebuilding torch/whisper/Chromium every time. BASE is pinned by the caller
# (terraform/main.tf → build/cloudbuild.render.yaml) to the current base image digest tag.
ARG BASE
FROM ${BASE}

COPY deck ./deck
ENV PYTHONPATH=/app

ENTRYPOINT ["uv", "run", "--no-dev", "python", "-m", "deck.infra.job"]
