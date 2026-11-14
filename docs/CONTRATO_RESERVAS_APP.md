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

### 3.1 Criação automática a partir do lobby

```http
POST /api/v1/bookings/from-lobby
Authorization: Bearer <access_token>
Content-Type: application/json

{"lobby_id": "uuid"}
```

O backend escolhe uma quadra ativa, compatível com o formato, dentro do raio do
lobby, com `payout_ready` e sem conflito de agenda. A ordenação é por distância
e depois por preço. Retorna `409 no_bookable_space` se não houver candidata.

### 3.2 Expediente do estabelecimento

O painel usa:

- `GET/POST /api/v1/organizations/{org}/venues/{venue}/business-hours`
- `DELETE /api/v1/organizations/{org}/venues/{venue}/business-hours/{id}`
- `GET/POST /api/v1/organizations/{org}/venues/{venue}/closures`
- `DELETE /api/v1/organizations/{org}/venues/{venue}/closures/{id}`

O T2 conta minutos úteis no expediente e respeita o teto em tempo corrido.

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

## 5. Erros relevantes

| Código | HTTP | Significado |
|---|---:|---|
| `payout_not_ready` | 409 | Estabelecimento sem chave/CNPJ ativo para repasse |
| `no_bookable_space` | 409 | Lobby sem quadra comercial elegível |
| `space_unavailable` | 409 | Agenda, blackout, hold ou reserva conflita |
| `insufficient_lead_time` | 409 | Não há tempo para T1/T2/T3 antes do início |
| `tickets_not_configured` | 409 | Faixa não tem tabela para o formato |
| `band_missing` | 409 | Janela sem faixa de preço |
| `booking_not_found` | 404 | Reserva inexistente ou fora do acesso |
| `forbidden` | 403 | Ator não participa do lobby/organização |

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

## 7. O que ainda falta no app e no painel

- App: usar a vitrine, escolher espaço/horário e chamar `POST /bookings`.
- App: exibir quitação por ingressos e a faixa congelada.
- Painel: cadastrar payout, editar faixa/cobertura e mostrar o repasse a receber.
- Ambos: notificações de prazo e nova reserva.
