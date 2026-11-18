# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Etapa 1: build do painel (Vite + pnpm).
# ---------------------------------------------------------------------------
FROM node:22-slim AS web

ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH

# O lockfile do web/ usa o formato 9; a versao fica fixada para builds
# reproduziveis. O Node 22 ja traz o corepack.
RUN corepack enable && corepack prepare pnpm@9.15.4 --activate

WORKDIR /app/web

COPY web/package.json web/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY web/ ./
RUN pnpm build

# ---------------------------------------------------------------------------
# Etapa 2: runtime com Python, Caddy e o painel ja compilado.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8080 \
    HOME=/app

# Caddy >= 2.8 pelo repositorio oficial (pacote arch-aware). A diretiva
# basic_auth usada em deploy/Caddyfile exige essa versao.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && curl -1sLf -o /tmp/caddy.key https://dl.cloudsmith.io/public/caddy/stable/gpg.key \
    && gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg /tmp/caddy.key \
    && curl -1sLf -o /etc/apt/sources.list.d/caddy-stable.list https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt \
    && chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg /etc/apt/sources.list.d/caddy-stable.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends caddy \
    && caddy version \
    && caddy version | grep -Eq 'v2\.([8-9]|[1-9][0-9])\.' \
    && rm -rf /var/lib/apt/lists/* /tmp/caddy.key

# O mesmo comando do CI: pip install -r requirements.lock, a partir de backend/.
WORKDIR /app/backend
COPY backend/requirements.lock ./
RUN python -m pip install --no-cache-dir -r requirements.lock

COPY backend/ ./
COPY --from=web /app/web/dist /srv/web
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY deploy/start.sh /app/start.sh

RUN groupadd --system app \
    && useradd --system --gid app --home-dir /app --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app/backend/var/media /app/.local/share/caddy /app/.config/caddy \
    && chmod +x /app/start.sh \
    && chown -R app:app /app /srv/web

USER app

EXPOSE 8080

ENTRYPOINT ["/app/start.sh"]
