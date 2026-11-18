FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PADDLE_PDX_CACHE_HOME=/models \
    PYTHONUNBUFFERED=1

RUN sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
      libgl1 libglib2.0-0 libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
COPY requirements.txt .
RUN pip install --no-cache-dir -i ${PIP_INDEX_URL} -r requirements.txt

COPY . .
RUN python -m app.warmup \
    && chmod -R a+rX /models \
    && useradd -m -u 10001 app \
    && mkdir -p /data/tmp && chown -R app /data/tmp

USER app
EXPOSE 8101
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8101", "--workers", "2"]
