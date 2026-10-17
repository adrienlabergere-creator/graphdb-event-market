FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts
# The agent's guardrails read the graph contract at runtime (allowed labels, relationships, properties).
COPY docs/GRAPH_CONTRACT.md ./docs/GRAPH_CONTRACT.md

# Code stays owned by root and read-only for the app, whatever file modes the build machine's checkout had.
RUN chmod -R a+rX /srv/app /srv/scripts /srv/docs

# Non-root user; it owns /srv/data, where the ingestion scripts cache the downloaded GDELT and FRED files.
RUN useradd --create-home appuser \
    && mkdir -p /srv/data \
    && chown appuser:appuser /srv/data
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
