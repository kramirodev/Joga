# ADR 0054 — Cache e rate limit do catálogo público

- **Status:** Aprovado em 2026-11-20.
- **Data:** 2026-11-20
- **Numeração:** esta ADR ocupa o número **0054**. A numeração está congelada:
  **0052** = payout da quadra pública, **0053** = modo demo sem PSP, **0054** =
  cache e rate limit do catálogo público.
- **Relaciona:** `docs/THREAT_MODEL.md`, `AGENTS.md` §4/§6/§7,
  `deploy/Caddyfile`, `backend/app/core/observability.py`,
  `backend/app/api/v1/discovery.py` e `backend/app/modules/ratelimit/`.

## Contexto

O achado P3-10 questiona o cache e o rate limit do catálogo público. O
middleware de observabilidade (`backend/app/core/observability.py`) define
`Cache-Control: no-store` em todas as respostas da API, depois de `call_next`.
Por isso, o header `Cache-Control: private, max-age=60` definido em
`backend/app/api/v1/discovery.py` na foto de quadra era código morto: o
middleware sempre o sobrescrevia.

O catálogo público (`GET /api/v1/catalog/sports` e
`GET /api/v1/catalog/visual`) é somente leitura, pequeno e alterado por ação
administrativa. Já as rotas de descoberta de estabelecimentos exigem sessão.
O Caddy padrão usado no demo (`deploy/Caddyfile`) não tem cache HTTP; faz apenas
proxy e basic auth do SPA.

O módulo de rate limit (`backend/app/modules/ratelimit/`) usa
`RateLimitCounter`, uma tabela com `SELECT ... FOR UPDATE` e incremento por
escopo/chave/janela. Aplicá-lo a requisições anônimas do catálogo criaria uma
escrita e um lock no PostgreSQL por leitura.

## Decisão

1. **Manter `Cache-Control: no-store`** em todas as respostas da API, inclusive
   no catálogo público. Não abrir exceção por rota nesta fase.
2. **Não cachear na borda** agora. Se houver cache no futuro, ele deve ser
   explícito no Caddy/CDN, com allowlist de paths públicos, TTL curto,
   invalidação e teste; nunca no app, porque o middleware sobrescreve headers de
   rota.
3. **Remover o header morto** `Cache-Control: private, max-age=60` de
   `discovery.py`; o header efetivo continua sendo o `no-store` do middleware.
4. **Não adicionar rate limit ao catálogo público**. O rate limit por tabela é
   inadequado para leitura anônima de alto volume. Se houver abuso, a mitigação
   deve ser de borda (proxy/CDN), não no app.

## Alternativas consideradas

- **Cache de borda via Caddy/CDN:** rejeitado nesta fase. O Caddy padrão não
  armazena cache; uma CDN/plugin adicionaria custo, invalidação e risco de
  servir catálogo desatualizado. O ganho não justifica a complexidade para um
  catálogo pequeno.
- **Rate limit no catálogo com `RateLimitCounter`:** rejeitado. Geraria escrita
  e lock no banco por requisição anônima, pior que o problema que tentaria
  resolver.
- **Exceção de `no-store` para `/api/v1/catalog/*`:** rejeitada. Uma regra ampla
  poderia alcançar rotas privadas futuras e aumentar o risco de cache de
  resposta autenticada.

## Consequências

- O catálogo público continua sem cache de borda e sem rate limit dedicado;
  risco aceito como **baixo**, por ser somente leitura, sem dado pessoal e sem
  alteração de estado.
- O `no-store` global permanece simples e seguro; não há nova exceção para
  esquecer de revisar.
- O código morto foi removido e o comentário no middleware registra a intenção.

## Gatilhos de revisão

- Adoção de CDN/edge cache.
- Aumento de tráfego anônimo ou custo de banco.
- Necessidade de catálogo realmente público/anônimo.
- Incidente de abuso.
- Mudança para cache: exigir allowlist de paths públicos, TTL curto, invalidação
  e teste; nunca cachear resposta autenticada.

## Evidências

- `backend/tests/test_venues_api.py::test_photo_upload_review_serving_and_removal`
  verifica `cache-control: no-store` na foto.
- `backend/tests/test_observability.py` verifica o header global.
- `ruff check` e `ruff format --check` passaram nos arquivos alterados.
