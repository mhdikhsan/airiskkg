# syntax=docker/dockerfile:1

# PAIR-AI Architecture Workbench — Flask app served by gunicorn.
#
#   docker build -t pair-ai .
#   docker run --rm -p 8000:8000 pair-ai      ->  http://localhost:8000
#
# The app loads ontology / shacl / example files at runtime relative to the
# repository root (airiskkg.paths._find_repo_root walks up until it finds both
# ontology/ and python/). So we copy the whole project and run the package from
# source on PYTHONPATH, which makes REPO_ROOT resolve to /app.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/python/src

WORKDIR /app

# Runtime dependencies (mirror python/pyproject.toml: rdflib + pyshacl + flask)
# plus gunicorn for serving. Installed before copying the source so this layer
# is cached across code changes.
RUN pip install --no-cache-dir rdflib pyshacl flask gunicorn

# Project source + the ontology / shacl / example data read at runtime
# (see .dockerignore for what is excluded from the build context).
COPY . /app

# Run unprivileged; the app only reads these files (default perms are readable).
RUN useradd --create-home --uid 1000 appuser
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/',timeout=4).status==200 else 1)"

# 2 workers, generous timeout (an assessment reloads the base ontology graph).
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "180", "airiskkg.webapp.app:app"]
