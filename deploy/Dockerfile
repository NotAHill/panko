# The hosted Panko: the front door plus everything each user's Panko needs (docs/SPEC-hosted.md, deploy/README.md).
# Builds for arm64 (Oracle's free Ampere machines) and amd64 alike. No user data goes into the image: it lives in
# the /srv/panko volume.
FROM python:3.12-slim-bookworm

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg poppler-utils sqlite3 ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.13.10 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/panko PATH=/opt/panko/bin:$PATH
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable --extra hub --extra host --extra mcp --extra apkg

# Optional: CAMeL Tools for checking Standard Arabic (pulls in torch, about 1 GB more). Build with
#   docker compose build --build-arg WITH_CAMEL=1
ARG WITH_CAMEL=0
RUN if [ "$WITH_CAMEL" = "1" ]; then \
      uv venv /opt/camel --python 3.12 && uv pip install --python /opt/camel/bin/python camel-tools \
      && CAMELTOOLS_DATA=/opt/camel-data /opt/camel/bin/camel_data -i morphology-db-msa-r13 ; fi
# without it the path doesn't exist and the checks go on with the references alone
ENV PANKO_CAMEL_PYTHON=/opt/camel/bin/python CAMELTOOLS_DATA=/opt/camel-data

RUN useradd --uid 1000 --create-home panko
USER panko
ENV PANKO_HOST_DATA=/srv/panko PANKO_HOST_BIND=0.0.0.0 PANKO_HOST_PORT=8800
EXPOSE 8800
HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8800/host/health')"
CMD ["panko", "host", "serve"]
