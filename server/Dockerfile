# ========= 构建阶段 =========
FROM python:3.11-slim-bullseye AS builder

ENV UV_SYSTEM_PYTHON=1 \
    UV_NO_CACHE=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv -i https://pypi.tuna.tsinghua.edu.cn/simple
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev


FROM python:3.11-slim-bullseye

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# 换源
RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list && \
    sed -i 's/security.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list

# 基础依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    supervisor \
    dumb-init \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*
#    curl ca-certificates gnupg \

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
COPY . /app

#ENTRYPOINT ["dumb-init", "--"]
#CMD ["python", "app.py"]
CMD ["supervisord", "-c", "/app/supervisord.conf"]
