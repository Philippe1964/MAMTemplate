# ==============================================================================
# Stage 1 : Build de l'application React 19 + TypeScript + Vite (App + /health-check)
# ==============================================================================
FROM node:22-alpine AS frontend-builder

RUN apk update && apk upgrade --no-cache

WORKDIR /frontend

COPY frontend/package.json ./
RUN npm install --no-audit --no-fund

COPY frontend/ ./
RUN npm run build

# ==============================================================================
# Stage 2 : Tiers Presentation — Reverse Proxy Nginx + React SPA (Hardened Alpine)
# ==============================================================================
FROM nginx:1.27-alpine AS runtime

RUN apk update \
    && apk upgrade --no-cache \
    && apk add --no-cache curl \
    && rm -rf /var/cache/apk/* \
    && rm -f /etc/nginx/conf.d/default.conf

COPY docker/presentation/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-builder /frontend/dist /usr/share/nginx/html
COPY docker/presentation/entrypoint.sh /entrypoint.sh

RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:80/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
