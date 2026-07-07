FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV U2NET_HOME=/app/.cache/rembg

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 libportaudio2 libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir rembg onnxruntime Pillow

RUN python -c "from rembg import new_session; new_session('u2net')"

COPY src ./src

RUN pip install --no-cache-dir -e ".[api,cloud,dev]"

CMD ["sh", "-c", "uvicorn bard_core.api:app --host 0.0.0.0 --port ${PORT}"]
