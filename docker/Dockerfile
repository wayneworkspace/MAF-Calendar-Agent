FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN useradd -m bot
WORKDIR /app
COPY app/requirements.txt .
RUN pip install -r requirements.txt
COPY --chown=bot:bot app/ .
RUN mkdir -p /app/logs /app/data && chown -R bot:bot /app/logs /app/data
USER bot
# data/token.json is created by `python auth.py` and mounted in (see docker-compose.yml)
HEALTHCHECK --interval=60s --timeout=10s --retries=3 CMD python -c "import os,time,sys; sys.exit(0 if time.time()-os.path.getmtime('logs/heartbeat')<180 else 1)"
CMD ["python", "main.py"]
