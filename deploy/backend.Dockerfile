# FastAPI backend. Build from the repository root:
#   docker build -f deploy/backend.Dockerfile -t ccs-screen-api .
#
# The image contains the code and the small SYNTHETIC demo dataset only. Real
# data is never baked in (see .dockerignore): mount it read-only and point
# CCS_DATA_DIR at the mount. CCS_DATA_DIR has no default here on purpose: an
# unset or missing directory makes /ready/existing-data answer 503 instead of
# silently serving the demo. User assessments need no dataset at all.
#
# Public demo: run with the variables in deploy/public-demo.env (no dataset,
# exact CORS origin, rate and concurrency limits). See docs/deployment.md.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m pip install ".[web,ingest]"
COPY demo ./demo

RUN useradd --create-home --uid 10001 app
USER app

# Hosting platforms usually set PORT; 8000 otherwise.
ENV PORT=8000
EXPOSE 8000
# /health is liveness; /ready is engine readiness (user assessments can be
# evaluated, independent of any dataset). Orchestrators should route on /ready.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:%s/ready' % os.environ.get('PORT', '8000')).status == 200 else 1)"
# One process: the opt-in rate and concurrency limits are per process (see
# docs/deployment.md). --proxy-headers takes the client address from the
# platform's proxy only for addresses in FORWARDED_ALLOW_IPS (uvicorn's default
# is 127.0.0.1). --no-access-log: the application writes no request paths or
# client addresses; the hosting platform's own proxy logs are separate.
CMD ["sh", "-c", "exec uvicorn ccs_screen.web.app:app --host 0.0.0.0 --port \"${PORT:-8000}\" --proxy-headers --no-access-log"]
