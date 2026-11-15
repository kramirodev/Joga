# Fase 13F — CEP e geocodificação de estabelecimento (Fase 1)

**Status:** implementado no backend em 2026-11-15.
**Depende de:** Fase 12/13 (estabelecimentos e quadras), Fase 4 (CEP do perfil).
**Não inclui:** mapa no painel, persistência de CEP no venue, provedor pago, backfill.

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

## Pendente

1. Persistir `postal_code`, `geocoding_source`, `geocoding_precision` e
   `geocoded_at` no venue (Fase 2).
2. Painel: CEP com máscara, endereço preenchido e pino ajustável.
3. Decidir mapa estático versus interativo e CSP.
4. Avaliar Nominatim/Google se a precisão de número for insuficiente.
5. Política de retenção/limpeza do cache.
