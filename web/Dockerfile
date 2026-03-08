########################################
# Stage 1 — 前端构建阶段 (Vue Build)
########################################
FROM node:20-alpine3.19 AS frontend-build

WORKDIR /qtr-frontend
ARG VITE_APP_BASE_API
ENV VITE_APP_BASE_API=$VITE_APP_BASE_API
ENV NODE_OPTIONS="--max-old-space-size=3072"

COPY package*.json ./
RUN npm ci --registry=https://registry.npmmirror.com \
    && npm cache clean --force
COPY . .
ENV GENERATE_SOURCEMAP=false
RUN npm run build:prod

########################################
# Stage 4 — 最终运行阶段，前端（干净镜像）
########################################
FROM nginx:alpine-slim
RUN apk add --no-cache gettext

COPY --from=frontend-build /qtr-frontend/dist /usr/share/nginx/html
COPY public/config.template.js /usr/share/nginx/html/config.template.js
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]