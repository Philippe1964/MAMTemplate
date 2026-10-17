# ==============================================================================
# Tiers Data : Base de données relationnelle PostgreSQL 17 Alpine (Hardened)
# ==============================================================================
FROM postgres:17-alpine

RUN apk update \
    && apk upgrade --no-cache \
    && rm -rf /var/cache/apk/*

COPY docker/data/init.sql /docker-entrypoint-initdb.d/01-init.sql
COPY docker/data/entrypoint-wrapper.sh /usr/local/bin/entrypoint-wrapper.sh

RUN sed -i 's/\r$//' /usr/local/bin/entrypoint-wrapper.sh \
    && chmod +x /usr/local/bin/entrypoint-wrapper.sh

EXPOSE 5432

HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=5 \
    CMD pg_isready -U "${POSTGRES_USER:-mamtemplate}" -d "${POSTGRES_DB:-mamtemplate}" || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint-wrapper.sh"]
CMD ["postgres"]
