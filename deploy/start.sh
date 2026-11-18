#!/bin/sh
# Sobe o ambiente de demonstracao em um unico container:
# migracoes -> uvicorn em loopback -> Caddy na porta publica.
set -e

PORT="${PORT:-8080}"
export PORT
export HOME="${HOME:-/app}"

cd /app/backend

mkdir -p "${JOGA_MEDIA_ROOT:-/app/backend/var/media}"

# Retry curto: o Session pooler do Supabase pode demorar no primeiro handshake.
attempt=1
while ! python -m alembic upgrade head; do
	if [ "$attempt" -ge 3 ]; then
		echo "migracao falhou apos 3 tentativas" >&2
		exit 1
	fi
	attempt=$((attempt + 1))
	sleep 5
done

# A API escuta apenas em loopback; quem expoe a porta publica e o Caddy.
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &

exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
