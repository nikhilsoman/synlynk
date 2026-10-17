FROM python:3.12-slim-bookworm

ARG AIDER_VERSION=0.86.2

RUN apt-get update \
    && apt-get install --yes --no-install-recommends git \
    && pip install --no-cache-dir "aider-chat==${AIDER_VERSION}" \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
ENTRYPOINT ["aider"]
