# Contrato de reservas para o aplicativo — Fase 13C

**Status:** contrato backend implementado em 2026-11-14; app mobile consumindo vitrine, criação de reserva, central de notificações e lotes; painel ainda pendente.
**Compatibilidade:** os campos novos são aditivos. Campos existentes não foram renomeados nem removidos.

## 1. Descobrir quadras reserváveis

```http
GET /api/v1/discovery/bookable-venues?page=1&page_size=20&city=Rio%20de%20Janeiro
Authorization: Bearer <access_token>
```

Resposta:

```json
{
  "venues": [
    {
      "id": "uuid",
      "organization_id": "uuid",
      "name": "Arena Centro",
      "city": "Rio de Janeiro",
      "state": "RJ",
      "address_line": "Rua ...",
      "latitude": -22.9,
      "longitude": -43.2,
      "timezone": "America/Sao_Paulo",
      "covered": true,
      "spaces_count": 2,
      "min_price_cents": 12000,
      "distance_km": 3.4,
      "photo_url": "/api/v1/discovery/bookable-venues/uuid/photos/uuid/content"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

`distance_km` é `null` quando o jogador não tem região definida. A coordenada é arredondada; o endpoint não expõe payout, CNPJ, chave Pix ou auditoria.

## 2. Detalhar quadra e horários

```http
GET /api/v1/discovery/bookable-venues/{venue_id}
Authorization: Bearer <access_token>
```

Resposta resumida:

```json
{
  "id": "uuid",
  "organization_id": "uuid",
  "name": "Arena Centro",
  "timezone": "America/Sao_Paulo",
  "photos": [
    {
      "id": "uuid",
      "caption": "Quadra coberta",
      "content_type": "image/jpeg",
      "content_url": "/api/v1/discovery/bookable-venues/uuid/photos/uuid/content"
    }
  ],
  "spaces": [
    {
      "id": "uuid",
      "name": "Quadra 1",
      "is_covered": true,
      "sports": [
        {
          "id": "uuid",
          "slug": "futebol",
          "name": "Futebol",
          "formats": [
            {
              "id": "uuid",
              "slug": "futebol-3x3",
              "name": "Futebol 3x3",
              "team_size": 3,
              "total_participants": 6,
              "tickets_by_band": {"economica_dia": 8}
            }
          ]
        }
      ],
      "availability": [
        {
          "weekday": 2,
          "start_time": "17:00:00",
          "end_time": "23:00:00",
          "price_cents": 12000,
          "slot_minutes": 60,
          "band": {
            "id": "uuid",
            "code": "economica_dia",
            "label": "Econômica dia",
            "max_price_cents": 12000
          }
        }
      ],
      "next_slots": [
        {
          "starts_at": "2026-11-17T18:00:00Z",
          "ends_at": "2026-11-17T19:00:00Z",
          "price_cents": 12000,
          "band_code": "economica_dia"
        }
      ]
    }
  ]
}
```

`next_slots` considera agenda semanal, bloqueios, holds e reservas ativas, além do tempo operacional mínimo. É referência, não garantia: a criação valida novamente de forma transacional.

## 3. Criar reserva

O app precisa de um lobby existente e do identificador da quadra. O endpoint atual continua sendo:

```http
POST /api/v1/bookings
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "lobby_id": "uuid",
  "organization_venue_id": "uuid",
  "venue_space_id": "uuid",
  "starts_at": "2026-12-15T18:00:00Z",
  "ends_at": "2026-12-15T19:00:00Z"
}
```

Regras:
- o ator precisa participar do lobby;
- a quadra, o estabelecimento e a organização precisam estar ativos;
- a janela precisa caber na agenda e não conflitar com hold/reserva/bloqueio;
- o estabelecimento precisa ter `payout_ready`;
- erro `409 payout_not_ready` quando falta CNPJ/chave Pix ou o status não é `active`;
- a criação é idempotente por `lobby_id`.

## 4. Campos aditivos em `BookingView`

```json
{
  "organization_venue_name": "Arena Centro",
  "venue_space_name": "Quadra 1",
  "format_id": "uuid",
  "format_name": "Futebol 3x3",
  "band_code": "economica_dia",
  "band_label": "Econômica dia",
  "tickets_per_seat": 8,
  "timezone": "America/Sao_Paulo",
  "participants": [
    {
      "user_id": "uuid",
      "settled_with": "tickets",
      "tickets_consumed": 8
    }
  ]
}
```

`band_code`, `tickets_per_seat` e `settled_with` são `null` quando não se aplicam. A reserva congela faixa e ingressos no momento da criação; reajuste posterior não altera a reserva.

`timezone` é o fuso IANA do estabelecimento. `starts_at`/`ends_at` continuam em UTC; o cliente deve formatar usando esse fuso, nunca o fuso do navegador.

### 4.1 Listas de reservas

```http
GET /api/v1/bookings?status=CONFIRMED&from=2026-11-01T00:00:00Z&to=2026-12-01T00:00:00Z&limit=50&offset=0
GET /api/v1/organizations/{organization_id}/bookings?status=CONFIRMED&from=...&to=...&limit=50&offset=0
```

```json
{
  "bookings": [],
  "total": 123,
  "limit": 50,
  "offset": 0
}
```

- `status` é opcional e usa os estados da reserva.
- `from` é inclusivo e `to` é exclusivo, ambos em UTC com offset ou `Z`.
- `limit` aceita 1–100; default 50. `offset` é >= 0.
- `total` é o total que satisfaz os filtros antes da paginação.
- Datas sem fuso retornam `422 invalid_time_range`.

## 5. Erros relevantes

| Código | HTTP | Significado |
|---|---:|---|
| `payout_not_ready` | 409 | Estabelecimento sem chave/CNPJ ativo para repasse |
| `space_unavailable` | 409 | Agenda, blackout, hold ou reserva conflita |
| `insufficient_lead_time` | 409 | Não há tempo para T1/T2/T3 antes do início |
| `tickets_not_configured` | 409 | Faixa não tem tabela para o formato |
| `band_missing` | 409 | Janela sem faixa de preço |
| `booking_not_found` | 404 | Reserva inexistente ou fora do acesso |
| `forbidden` | 403 | Ator não participa do lobby/organização |
| `invalid_time_range` | 422 | `from`/`to` sem fuso, invertidos ou iguais |
| `validation_error` | 422 | Corpo/query inválido; ver `fields` abaixo |

Erros de schema Pydantic usam um envelope estável:

```json
{
  "detail": {
    "code": "validation_error",
    "message": "Dados inválidos",
    "fields": [
      { "field": "body.name", "code": "string_too_short", "message": "..." }
    ]
  }
}
```

`field` usa prefixo `body.`, `query.` ou `path.`. O valor enviado não é ecoado.

## 6. Central de notificações

```http
GET /api/v1/me/notifications?unread_only=false&limit=30&offset=0
Authorization: Bearer <access_token>
```

```json
{
  "notifications": [
    {
      "id": "uuid",
      "kind": "booking_confirmed",
      "title": "Reserva confirmada",
      "body": "Todos os participantes quitaram a vaga.",
      "data": {"booking_id": "uuid"},
      "created_at": "2026-11-14T18:00:00Z",
      "read_at": null
    }
  ],
  "unread_count": 1,
  "limit": 30,
  "offset": 0
}
```

- `GET /api/v1/me/notifications/unread-count`
- `POST /api/v1/me/notifications/{id}/read`
- `POST /api/v1/me/notifications/read-all`

A notificação é persistida antes do push. O app deve tratar a lista como fonte de histórico e o push apenas como aviso.

## 7. Moderação (Fase 17A)

```http
POST /api/v1/moderation/reports
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "target_user_id": "uuid",
  "lobby_id": "uuid",
  "category": "THREAT",
  "description": "Ameaça no chat",
  "message_ids": ["uuid"]
}
```

- `message_ids` aceita até 5 mensagens do alvo no mesmo lobby.
- Categorias: `HARASSMENT`, `HATE`, `THREAT`, `SEXUAL`, `SPAM`, `OTHER`.
- A denúncia fica `OPEN` para revisão humana; não há punição automática.
- Histórico do denunciante: `GET /api/v1/moderation/reports/me`.
- Medidas recebidas: `GET /api/v1/moderation/actions/me`.
- Recurso: `POST /api/v1/moderation/actions/{action_id}/appeal`.
- Tipos de medida: `WARNING`, `RESTRICT_RANKED` e `SUSPEND_TEMP` (1–30 dias).
- A conta suspensa não usa a API normalmente. A reativação ocorre ao fim do prazo.

Contrato de suspensão para o app:

- `POST /api/v1/auth/refresh` de conta suspensa rotaciona a sessão e responde `200` com `user.status = "suspended"`. O app deve preservar a sessão, mostrar a tela de suspensão e usar esse access token apenas nas duas rotas de contestação abaixo. Refresh inválido/expirado continua `invalid_refresh_token`.
- `GET /api/v1/auth/me` e as demais rotas comuns respondem `401 invalid_token` para conta suspensa.
- Exceções: `GET /api/v1/moderation/actions/me` e `POST /api/v1/moderation/actions/{action_id}/appeal` aceitam a sessão suspensa para o jogador ver a própria medida e contestá-la. A autorização continua limitada ao alvo da medida; tentar contestar a medida de outro usuário retorna `404`.
- Severidade, prioridade e identidade do denunciante não são expostas ao app.

A triagem é determinística (`rules_v1`), sem IA paga. A revisão é humana e interna.

### 7.1 Painel interno de moderação (não é contrato mobile)

Estas rotas exigem conta em `moderation_operators`; conta comum recebe
`403 moderator_required`. A gestão de operadores exige papel `ADMIN`.

```http
GET  /api/v1/moderation/me
GET  /api/v1/moderation/queue?status_filter=OPEN&limit=50&offset=0
GET  /api/v1/moderation/reports/{report_id}
POST /api/v1/moderation/reports/{report_id}/decision
GET  /api/v1/moderation/appeals?status_filter=OPEN
POST /api/v1/moderation/appeals/{appeal_id}/decision
GET  /api/v1/moderation/operators
POST /api/v1/moderation/operators
DELETE /api/v1/moderation/operators/{user_id}
```

- Decisão: `DISMISS`, `WARN`, `RESTRICT_RANKED` ou `SUSPEND_TEMP`; justificativa
  obrigatória e `days` de 1–30 para suspensão.
- Recurso: `ACCEPTED` ou `REJECTED`, com justificativa.
- Nova denúncia gera notificação persistida `moderation_report` para os
  operadores ativos.
- Novo recurso gera `moderation_appeal` para os operadores ativos.
- A decisão do recurso gera `moderation_appeal_result` para o jogador.

### 7.2 Sessão web e capacidades

`POST /api/v1/auth/web/registration`, `/login` e `/refresh` devolvem
`capabilities` junto da sessão:

```json
{
  "user": { "id": "uuid", "status": "active" },
  "capabilities": ["moderation.read", "moderation.manage"]
}
```

- Conta comum: `[]`.
- `MODERATOR`: `["moderation.read"]`.
- `ADMIN`: `["moderation.read", "moderation.manage"]`.
- O painel usa isso para esconder o link; a autorização real continua no servidor.

### 7.3 Totais em listas do painel

Os envelopes abaixo incluem `total` (antes da paginação) além de `limit` e
`offset`:

- `GET /organizations/{id}/financial/receivables`
- `GET /organizations/{id}/financial/statement`
- `GET /organizations/{id}/financial/disputes`
- `GET /organizations/{id}/audit`
- `GET /bookings` e `GET /organizations/{id}/bookings`

## 8. O que ainda falta no app e no painel

- App: usar a vitrine, escolher espaço/horário e chamar `POST /bookings`.
- App: exibir quitação por ingressos e a faixa congelada.
- Painel: cadastrar payout, editar faixa/cobertura e mostrar o repasse a receber.
- Ambos: notificações de prazo e nova reserva.

## 9. CEP e geocodificação de estabelecimento (Fase 1)

```http
GET /api/v1/geo/postal-codes/20541-004?number=1200
Authorization: Bearer <access_token>
```

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

- `postal_code` aceita 8 dígitos com ou sem hífen.
- `number` é opcional (até 20 caracteres; `s/n` aceito) e não altera o `POST` de venue.
- `precision`: `street`, `venue`, `approximate` ou `unresolved`.
- `latitude`/`longitude` podem ser `null` apenas com `precision: "unresolved"`.
- O `POST /organizations/{id}/venues` continua exigindo `latitude`/`longitude`; o painel resolve antes e envia os números.
- Cache persistente por CEP+número+versão do provedor, TTL de 30 dias.
- Rate limit de 30 consultas/minuto por usuário; `429 rate_limited` com `Retry-After`.
- Provedor desta fase: BrasilAPI CEP v2, que já devolve endereço e coordenadas. Nominatim/Google ficam como evolução atrás da mesma interface.

| HTTP | `code` |
|---:|---|
| 400 | `invalid_postal_code` |
| 404 | `postal_code_not_found` |
| 422 | `postal_code_ambiguous` (reservado; não emitido nesta fase) |
| 429 | `rate_limited` |
| 502 | `geocoding_provider_error` |
| 504 | `geocoding_timeout` |
