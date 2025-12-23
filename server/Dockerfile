FROM python:3.11-slim

RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list && \
    sed -i 's|security.debian.org/debian-security|mirrors.ustc.edu.cn/debian-security|g' /etc/apt/sources.list && \
    apt-get update && apt-get install --no-install-recommends -y nodejs npm wkhtmltopdf supervisor dumb-init && \
    npm install --registry=https://registry.npmmirror.com jsonpath && \
    npm install --registry=https://registry.npmmirror.com jmespath && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app

ENTRYPOINT ["dumb-init", "--"]
CMD ["supervisord", "-c", "/app/supervisord.conf"]
