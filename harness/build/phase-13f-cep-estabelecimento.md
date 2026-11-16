# Fase 13F — CEP e geocodificação de estabelecimento (Fases 1 e 2)

**Status:** Fases 1 e 2 implementadas no backend em 2026-11-15.
**Depende de:** Fase 12/13 (estabelecimentos e quadras), Fase 4 (CEP do perfil).
**Não inclui:** mapa no painel, provedor pago, backfill retroativo de endereço.

## Problema

O cadastro de estabelecimento exigia latitude e longitude digitadas pelo vendedor.
O banco aceitava nulo, mas a API exigia coordenadas, o que produzia pins errados e
degradava a descoberta por distância.

## Decisão da Fase 1

- Endpoint novo `GET /api/v1/geo/postal-codes/{postal_code}?number=...`.
- Autenticado, sem alterar `POST /organizations/{id}/venues`.
- Provedor reaproveitado: BrasilAPI CEP v2, que já devolve endereço e coordenadas.
- Nominatim/Google ficam atrás da mesma interface para uma fase posterior.
- Cache persistente em `postal_code_cache`, chave CEP+número+versão do provedor,
  TTL de 30 dias.
- Rate limit de 30 consultas/minuto por usuário, usando o serviço existente.
- Timeout de 3 s no provedor.
- `number` é opcional e hoje não altera a coordenada; fica no contrato para
  provedores futuros com geocodificação por número.

## Contrato

```http
GET /api/v1/geo/postal-codes/20541-004?number=1200
```

Resposta:

```json
{
  "postal_code": "20541004",
  "street": "Rua Barão de Mesquita",
  "neighborhood": "Tijuca",
  "city": "Rio de Janeiro",
  "state": "RJ",
  "country": "BR",
  "latitude": -22.9234,
  "longitude": -43.2456,
  "precision": "street",
  "source": "brasilapi",
  "resolved_at": "2026-11-15T12:00:00Z"
}
```

- `precision`: `street`, `venue`, `approximate` ou `unresolved`.
- `latitude`/`longitude` são nulos apenas em `unresolved`.
- Erros: `invalid_postal_code` (400), `postal_code_not_found` (404),
  `rate_limited` (429), `geocoding_provider_error` (502),
  `geocoding_timeout` (504).
- `postal_code_ambiguous` (422) fica reservado; o provedor atual não o emite.

## Modelo

Migração `c5d6e7f8a9b0`:

- `postal_code_cache` com `cache_key`, `postal_code`, `number`, `provider`,
  `payload` JSONB, `resolved_at`, `expires_at` e `created_at`;
- índices por `expires_at` e `postal_code`.

A linha expirada é removida na próxima leitura do mesmo CEP.

## Fase 2 — persistência no estabelecimento

Migração `e7f8a9b0c1d2` adiciona a `organization_venues`:

| Coluna | Tipo | Regra |
|---|---|---|
| `postal_code` | varchar(8) | opcional, gravado só com dígitos |
| `geocoding_source` | varchar(40) | opcional, minúsculas (`brasilapi`) |
| `geocoding_precision` | varchar(20) | `street`, `venue`, `approximate` ou `manual` |
| `geocoded_at` | timestamptz | opcional, gravado pelo servidor |

- `latitude`/`longitude` continuam obrigatórias na API e validadas por faixa.
- O `POST`/`PATCH` aceitam `postal_code`, `geocoding_source` e
  `geocoding_precision`; o `GET` devolve os quatro campos novos.
- Sem proveniência, a coordenada é `manual`.
- `street`, `venue` e `approximate` exigem `geocoding_source`; o servidor grava
  `geocoded_at`.
- `manual` zera `geocoding_source` e `geocoded_at`.
- Mudar `latitude`, `longitude` ou `postal_code` sem reenviar proveniência
  rebaixa para `manual`: o pino ajustado é a autoridade final.
- O backfill da migração marca como `manual` os registros que já têm coordenada.
- `venue.created` e `venue.updated` continuam auditados; a trilha inclui CEP e
  mudanças de proveniência.
- Valores fora do contrato respondem `422 invalid_input` (serviço) ou
  `422 validation_error` com `fields` (enum/limite de tamanho).

## Segurança e privacidade

- Chave/URL do provedor não sai do servidor.
- CEP é dado comercial; não é registrado junto de IP/telefone em log.
- Coordenadas recebidas no `POST` continuam validadas por faixa.
- Cache contém apenas endereço comercial e coordenadas, sem dado pessoal.
- Erros não ecoam corpo, URL ou chave do provedor.

## Testes

`backend/tests/test_geo_api.py` cobre:

- autenticação obrigatória;
- CEP com e sem hífen;
- contrato completo da resposta;
- cache hit sem segunda chamada ao provedor;
- 400/404/502/504;
- `unresolved` com coordenadas nulas;
- rate limit 429 com `Retry-After`.

Nenhum teste chama provedor externo; o resolver é injetado.

`backend/tests/test_organizations.py::test_venue_postal_code_and_geocoding_provenance`
cobre normalização do CEP, persistência da proveniência, rebaixamento para
`manual`, cadastro sem CEP, CEP inválido e proveniência incompleta.

Suíte backend: **485 passed, 29 skipped**; `ruff check`, `ruff format --check` e
`mypy app` limpos; Alembic no head `e7f8a9b0c1d2` com `alembic check` limpo.

## Pendente

1. Painel: CEP com máscara, endereço preenchido e pino ajustável.
2. Decidir mapa estático versus interativo e CSP.
3. Avaliar Nominatim/Google se a precisão de número for insuficiente.
4. Política de retenção/limpeza do cache.
5. Backfill de endereço/CEP para estabelecimentos existentes (opcional).
