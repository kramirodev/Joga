# Contrato de reservas para o aplicativo — Fase 13C

**Versão:** v2026-11-20
**Status:** contrato backend implementado em 2026-11-14; identidade visual, catálogo administrável de esportes, administração de usuários, bloqueio de compra de tickets e fila multi-entrada (ADR 0057) adicionados em 2026-11-20. App mobile consumindo vitrine, criação de reserva, central de notificações e crédito; painel parcialmente implementado. A ADR 0049 altera a camada de preço/conta; a 14E já persiste o preço em duas linhas. A gratuidade da quadra pública (ADR 0055) e a enquete de escolha de quadra (ADR 0056) estão registradas aqui como **design a implementar**.
**Compatibilidade:** os campos novos são aditivos. Campos existentes não foram renomeados nem removidos.

## 0. Preço, tickets e NFS-e (ADR 0049)

- A substância jurídica e contábil é **crédito em reais**; o ticket é a **unidade de consumo** da tabela 2D, não uma conversão do real.
- O saldo em reais não é exibido como carteira.
- Antes da confirmação, o app mostra o valor do espaço, a taxa de intermediação e a tabela de conversão tickets ↔ faixa/valor.
- A NFS-e materializa o valor: locação/uso pelo fornecedor e intermediação pelo JOGA.
- `price_cents` continua sendo o valor do espaço (compatibilidade). A reserva nova grava também `venue_price_cents`, `fee_cents`, `fee_percent_applied`, `total_cents` e `pricing_version`, congelados na criação; `venue_price_cents + fee_cents == total_cents`.
- A contagem da vaga é `k = tickets_per_seat`, resolvida pela tabela 2D (faixa × formato) e congelada na reserva. 5x5, 6x6 e 3x3 (futevôlei) são padrão; 4x4 e menores usam `ceil((V + taxa) / (n × 3,10))`.
- O ticket é calibrado em R$ 3,10, mas **não é convertido em real no consumo**. No caminho por tickets, o ledger debita `k × 310`, credita a quadra com `space_charge_cents` e o restante em `fee_revenue`.
- O preço pago no pacote é caixa e vira `player_credit`; não existe conta de prêmio nem desconto. O excedente do pacote acima de R$ 3,10 fica como crédito (passivo).
- `band_code`/`tickets_per_seat` são a unidade de consumo/exibição; o preço jurídico continua sendo valor da quadra + taxa.
- **Exceção — quadra pública:** a quadra pública é **gratuita** (ADR 0055). Não tem valor de espaço, taxa, faixa, contagem de tickets, cobrança nem repasse; a reserva registra `venue_price_cents = 0`, `fee_cents = 0` e `total_cents = 0`, sem lançamento no ledger. **A implementar.**
- **Atenção:** em `BookingView.payments[]`, `participant_id` é o id da **vaga** (`booking_participants`), não o `user_id`. O app deve localizar o pagamento pelo participante correspondente, não comparar com `session.userId`.

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
  "price_cents": 15000,
  "venue_price_cents": 15000,
  "fee_cents": 3000,
  "fee_percent_applied": 2000,
  "total_cents": 18000,
  "pricing_version": "adr0049_v1",
  "timezone": "America/Sao_Paulo",
  "participants": [
    {
      "user_id": "uuid",
      "contribution_cents": 2480,
      "space_charge_cents": 2000,
      "fee_charge_cents": 480,
      "funding_source": "credit",
      "settled_with": "tickets",
      "tickets_consumed": 8
    }
  ]
}
```

`band_code`, `tickets_per_seat` e `settled_with` são `null` quando não se aplicam. A reserva congela faixa, `tickets_per_seat` e preço no momento da criação; reajuste posterior não altera a reserva.

`fee_percent_applied` está em **basis points** (`2000` = 20%). A taxa é calculada no servidor com percentual uniforme e piso configuráveis; o cliente nunca envia preço nem taxa.

No caminho por tickets, `contribution_cents = k × 310`, `space_charge_cents` é a cota exata da quadra e `fee_charge_cents = contribution_cents − space_charge_cents` (o valor do JOGA, não 20% fixo). No Pix, `contribution_cents` é o preço congelado e `fee_charge_cents` é a taxa de 20%. `Σ space_charge_cents == venue_price_cents`.

Quando a vaga é paga por passe/grátis/admin, `funding_source` identifica a fonte, `player_credit` não é debitado e a confirmação lança a quadra contra `pass_revenue` (passe) ou `promo_expense` (grátis/admin). Nesse caso a notificação mostra a linha da quadra e a fonte (“Cota do passe”/“Cortesia”), sem sugerir que o JOGA cobrou a taxa do jogador.

### 4.1 Crédito e franquia

- Crédito comprado (`ticket_lots.source = "purchase"`) **não expira** e não é afetado pelo job de expiração. Os lotes continuam em tickets.
- O ticket é a unidade de consumo da tabela 2D; o valor de referência é R$ 3,10. O preço pago no pacote vira `player_credit` (caixa) e o lote sobe em tickets. Não há prêmio nem desconto.
- `ticket_lots.source = "pass"` é franquia mensal: usa `period` (`YYYY-MM`), não `expires_at`, não acumula e não vira crédito.
- `free_level`/`admin` usam `expires_at` quando existir; ingresso grátis de nível expira com a temporada.
- A ordem de consumo é `pass → free_level → admin → purchase → refund`.
- `GET /api/v1/me/tickets` devolve `period` em cada lote (aditivo). `balance` continua em tickets de exibição; o saldo monetário não é exibido como carteira.
- A resposta do wallet mantém `source`, agora sempre `ledger`: tickets dos lotes + passe/grátis/admin utilizáveis, com validação do caixa `player_credit`. A flag `JOGA_TICKET_BALANCE_SOURCE` foi removida na Etapa 9.
- Conta ausente para lote existente, caixa divergente ou saldo negativo responde `503 balance_unavailable`. O app não deve tratar esse erro como saldo zero; deve mostrar indisponibilidade e tentar novamente.
- Reservas anteriores à 14E têm `pricing_version = "legacy_v0"`, `fee_cents = 0` e `total_cents = venue_price_cents`. Elas não são relançadas no ledger.

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

Texto de uma linha com controles/NUL (`\x00`–`\x1f`, `\x7f`) responde
`422 validation_error`. Texto multilinha (bio, chat, descrições, evidência de
contestação e notas) aceita `\n`, normaliza `\r\n`/`\r` para `\n`, mas continua
rejeitando NUL/demais controles, bidi e zero-width. `display_name` também rejeita
CR/LF e marcas invisíveis. Nada disso chega ao banco; o app deve limpar o campo
antes de reenviar. Acentos e emoji seguem aceitos.

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

- `POST /api/v1/auth/refresh` de conta suspensa rotaciona a sessão e responde `200` com `user.status = "suspended"`. O app deve preservar a sessão, mostrar a tela de suspensão e usar esse access token apenas nas rotas de contestação abaixo. Refresh inválido/expirado continua `invalid_refresh_token`.
- `GET /api/v1/auth/me` e as demais rotas comuns respondem `401 invalid_token` para conta suspensa.
- Exceções: `GET /api/v1/moderation/actions/me`, `GET /api/v1/moderation/appeals/me` e `POST /api/v1/moderation/actions/{action_id}/appeal` aceitam a sessão suspensa para o jogador ver a própria medida, consultar o resultado do recurso e contestá-la. A autorização continua limitada ao alvo da medida/recurso; tentar contestar a medida de outro usuário retorna `404`.
- `GET /api/v1/moderation/appeals/me` devolve `status` (`OPEN`, `ACCEPTED`, `REJECTED`), `decided_at` e `decision_reason`, permitindo mostrar uma rejeição sem esperar o fim da suspensão.
- `GET /api/v1/me/notifications` continua exigindo conta ativa.
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
  operadores ativos, no canal interno `moderation`.
- Novo recurso gera `moderation_appeal` para os operadores ativos, no canal
  interno `moderation`.
- A decisão do recurso gera `moderation_appeal_result` para o jogador, no canal
  `player`.
- A central do jogador (`GET /me/notifications`) lista apenas o canal `player`;
  notificações internas não aparecem no app e não geram push para o jogador.
- O painel tem central própria no canal interno, protegida por `get_moderator`
  (conta comum recebe `403 moderator_required`):

```text
GET  /api/v1/moderation/notifications?unread_only=false&limit=30&offset=0
GET  /api/v1/moderation/notifications/unread-count
POST /api/v1/moderation/notifications/{notification_id}/read
POST /api/v1/moderation/notifications/read-all
```

- Os quatro endpoints operam sempre `channel = "moderation"` e não aceitam
  parâmetro de canal.
- `GET` devolve o mesmo envelope da central do jogador (`notifications`,
  `unread_count`, `limit`, `offset`), com contagem só do canal interno.
- `read-all` marca apenas notificações internas do próprio operador.
- ID de outro operador ou do canal `player` responde
  `404 notification_not_found`.

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
- Painel: consumir os campos novos do Financeiro (preço em duas linhas,
  comprovante, prazo de contestação, comissão separada e NFS-e placeholder)
  descritos na seção 10.
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
- Desde a Fase 2, o venue aceita `postal_code`, `geocoding_source` e `geocoding_precision`; `GET`/`PATCH` devolvem também `geocoded_at`. Ver o contrato do estabelecimento abaixo.
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

### Estabelecimento com CEP e proveniência (Fase 2)

`POST /api/v1/organizations/{organization_id}/venues` e `PATCH .../venues/{venue_id}` aceitam, além dos campos atuais:

| Campo | Regra |
|---|---|
| `postal_code` | opcional; 8 dígitos com ou sem hífen (`20541-004`) — o backend grava só `20541004` |
| `geocoding_source` | opcional; minúsculas, até 40 caracteres (`brasilapi`, `viacep+nominatim`) |
| `geocoding_precision` | opcional; `street`, `venue`, `approximate` ou `manual` |

Regras:

- `latitude`/`longitude` continuam obrigatórias no `POST` e validadas por faixa.
- Sem `geocoding_precision`, a coordenada é gravada como `manual`.
- `street`, `venue` e `approximate` exigem `geocoding_source`; o backend grava `geocoded_at` no momento da gravação.
- `manual` descarta o `geocoding_source` e grava `geocoded_at = null`.
- Se `latitude`, `longitude` ou `postal_code` mudarem sem proveniência no mesmo payload, a coordenada volta a `manual` — o pino ajustado é a autoridade final.
- `postal_code` ou proveniência inválidos respondem `422 invalid_input`; precision fora do enum responde `422 validation_error` com `fields`.
- `GET`, `POST` e `PATCH` devolvem `postal_code`, `geocoding_source`, `geocoding_precision` e `geocoded_at` (além dos campos anteriores).

### Expediente do estabelecimento (Fase 13E)

O painel lê e edita o expediente sem apagar e recriar a janela:

```http
GET   /api/v1/organizations/{organization_id}/venues/{venue_id}/business-hours
POST  /api/v1/organizations/{organization_id}/venues/{venue_id}/business-hours
PATCH /api/v1/organizations/{organization_id}/venues/{venue_id}/business-hours/{business_hour_id}
DELETE /api/v1/organizations/{organization_id}/venues/{venue_id}/business-hours/{business_hour_id}
```

`POST` recebe `weekday`, `opens_at` e `closes_at`; `PATCH` aceita qualquer
subconjunto desses três campos e mantém os demais. Regras válidas nos dois:

- `weekday` entre 1 (segunda) e 7 (domingo); `opens_at < closes_at`.
- Não pode existir outra janela do mesmo dia com o mesmo `opens_at` nem com
  sobreposição de horário. A violação responde `409 business_hour_conflict`.
- Valor inválido responde `422 invalid_input`.
- A escrita exige a capacidade `venues:manage` escopada pela organização. Membro
  de outra organização recebe `404`.
- `PATCH` grava auditoria `venue_business_hour.updated` com `before` e `after`.

**Prazos T2 não são recalculados.** `booking_timers` e `response_due_at` são
gravados quando o T2 começa, a partir do expediente vigente naquele instante.
Editar o expediente depois não altera reservas já em andamento; a mudança vale
para os próximos T2.

## 10. Interface financeira do fornecedor (Fase 15 sobre o ledger em reais)

Escopo: painel do fornecedor e operação interna. O app mobile do jogador **não**
consome estes endpoints e não exibe saldo em reais como carteira.

Autorização: toda rota é escopada pela organização no servidor. Leitura exige
`financial:read` (`OWNER`, `ADMIN`, `OPERATOR`); abrir contestação exige
`financial:manage` (`OWNER`, `ADMIN`); decidir contestação exige
`financial:manage` **e** o usuário em `JOGA_REVIEW_OPERATORS`. Membro de outra
organização recebe `404`; capacidade ausente recebe `403`.

### 10.1 Endpoints

| Método | Rota | Capacidade |
|---|---|---|
| `GET` | `/api/v1/organizations/{org}/financial/summary` | `financial:read` |
| `GET` | `/api/v1/organizations/{org}/financial/receivables?status=` | `financial:read` |
| `GET` | `/api/v1/organizations/{org}/financial/statement?limit=&offset=` | `financial:read` |
| `GET` | `/api/v1/organizations/{org}/financial/commission?from=&to=&limit=&offset=` | `financial:read` |
| `GET` | `/api/v1/organizations/{org}/bookings/{booking}/financial` | `financial:read` |
| `GET` | `/api/v1/organizations/{org}/financial/disputes?status=` | `financial:read` |
| `POST` | `/api/v1/organizations/{org}/financial/disputes` | `financial:manage` |
| `GET` | `/api/v1/organizations/{org}/financial/disputes/{id}` | `financial:read` |
| `POST` | `/api/v1/organizations/{org}/financial/disputes/{id}/decision` | `financial:manage` + operador |

### 10.2 Preço em duas linhas

Toda linha de extrato e todo recebível trazem `venue_price_cents`, `fee_cents` e
`total_cents` congelados na reserva, com
`venue_price_cents + fee_cents == total_cents`. O valor do fornecedor **nunca** é
receita do JOGA:

- `financial/summary` devolve `venue_price_cents` (fornecedor) e
  `joga_fee_cents` (comissão) em campos distintos; não somar os dois.
- `financial/commission` devolve, por reserva, `venue_price_cents`, `fee_cents` e
  `total_cents`, e em `totals` somente `venue_price_cents`, `joga_fee_cents` e
  `total_cents`. A comissão é `joga_fee_cents`; o restante é obrigação do
  fornecedor.
- O ticket continua sendo unidade de exibição; nenhum campo em reais pode ser
  apresentado como carteira do jogador.

### 10.3 Semântica por endpoint

**`GET financial/receivables`** — agenda de repasses:

| Campo | Semântica |
|---|---|
| `booking_id`, `release_id` | Reserva e obrigação de repasse |
| `amount_cents` | Valor do fornecedor devido (`venue_price_cents`) |
| `status` | `PENDING`, `RELEASED`, `FAILED` ou `REVERSED` |
| `eligible_at` | `starts_at + 2 h` (ADR 0040) |
| `released_at` | Instante do repasse simulado; `null` enquanto pendente |
| `venue_price_cents`, `fee_cents`, `total_cents` | Preço congelado em duas linhas |
| `receipt_reference` | Comprovante do repasse. Em produção: `bank:<e2e_id>` ou `psp:<id>`, com PDF do JOGA em storage privado. No protótipo/teste: `simulated:<release_id>`; `null` enquanto pendente |
| `dispute_deadline` | Snapshot persistido de `eligible_at + JOGA_DISPUTE_WINDOW_HOURS` (72 h); não é recalculado |
| `has_open_dispute`, `dispute_id` | Contestação aberta suspende a liberação |
| `reason` | Motivo de falha, reversão ou liberação |

**`GET financial/statement`** — extrato do fornecedor, uma linha por transação
contábil que afeta a conta da quadra:

| Campo | Semântica |
|---|---|
| `id` | `ledger_transactions.id` |
| `entry_type` | `PAYMENT_CONFIRMED` (parte da quadra na confirmação), `PAYMENT_REFUNDED` (devolução) ou `VENUE_RELEASE` (repasse) |
| `direction` | `CREDIT` ou `DEBIT`; `amount_cents` é sempre positivo |
| `release_id` | Preenchido somente em `VENUE_RELEASE` |
| `venue_price_cents`, `fee_cents`, `total_cents` | Preço congelado da reserva |
| `booking_payment_id` | Sempre `null`; o fato contábil é a reserva |
| `status` | Sempre `POSTED` |
| `details` | `{ "kind", "idempotency_key" }` |

`PAYMENT_CONFIRMED` já é a parte da quadra; a comissão do JOGA não aparece como
linha do extrato do fornecedor.

**`GET financial/commission`** — relatório por reserva confirmada. `from` e `to`
são ISO 8601 e filtram `confirmed_at` (inclusivo). `totals.bookings` conta as
reservas do período.

**`GET organizations/{org}/bookings/{booking}/financial`** — detalhe:

```json
{
  "booking_id": "uuid",
  "pricing": {
    "venue_price_cents": 40000,
    "fee_cents": 8000,
    "fee_percent_applied": 2000,
    "total_cents": 48000,
    "pricing_version": "adr0049_v1"
  },
  "release": { "...": "mesmo formato de receivable ou null" },
  "dispute": { "...": "última contestação ou null" },
  "fiscal_document": {
    "id": "uuid",
    "status": "pending_manual",
    "amount_cents": 40000,
    "number": null,
    "provider_ref": null,
    "issued_at": null
  },
  "ledger": [ "..." ],
  "refunds": [ "..." ]
}
```

`fiscal_document` é a **exibição do placeholder**: `pending_manual` significa
intenção registrada, sem emissão de NFS-e. `null` quando a reserva não tem
documento (por exemplo, `JOGA_FISCAL_MODE=disabled`). Cada item de `ledger` tem
o mesmo formato de `statement.entries[]`, incluindo `release_id`,
`venue_price_cents`, `fee_cents` e `total_cents`.

### 10.4 Contestações

- `POST .../disputes` recebe `{ "booking_id", "reason", "evidence"? }`.
- Só é aceita enquanto a liberação está `PENDING` e antes de
  `dispute_deadline`. Depois disso: `409 release_not_contestable` ou
  `409 dispute_window_expired`.
- Uma contestação `OPEN` por reserva; duplicata responde
  `409 dispute_already_open`.
- `POST .../disputes/{id}/decision` recebe
  `{ "decision": "ACCEPTED" | "REJECTED", "reason": "..." }` (1–500 caracteres).
  Exige operador interno em `JOGA_REVIEW_OPERATORS`; usuário comum com
  `financial:manage` recebe `403 operator_not_authorized`.
- A decisão grava `decided_by`, `decided_at`, `decision_reason` e auditoria
  append-only `financial.dispute_decided`. `ACCEPTED` libera o repasse
  (`RELEASED`); `REJECTED` mantém a liberação pendente para o worker.
- Janela de contestação: `JOGA_DISPUTE_WINDOW_HOURS` = **72 h**, decidida em
  2026-11-17 e persistida como snapshot em `venue_releases.dispute_deadline` e
  `financial_disputes.deadline_at`. Mudar a configuração não altera prazos já
  gravados.
- `DisputeView` inclui `deadline_at` (o snapshot da contestação).

### 10.5 `participant_id` em `payments[]`

Em `BookingView.payments[]`, **`participant_id` é o id da vaga**
(`booking_participants`), **não** o `user_id`. O app deve localizar o pagamento
pelo participante correspondente na própria reserva, nunca comparar
`participant_id` com `session.userId`. O `user_id` do participante está em
`BookingView.participants[]`, não em `payments[]`.

### 10.6 Erros

| HTTP | `code` |
|---:|---|
| 403 | `forbidden`, `operator_not_authorized` |
| 404 | `organization_not_found`, `dispute_not_found`, `booking_not_found`, `release_not_found` |
| 409 | `dispute_already_open`, `dispute_not_open`, `release_not_contestable`, `dispute_window_expired`, `cancellation_closed` |
| 422 | `validation_error` |

### 10.7 Cancelamento, substituição e no-show (decisão de 17/11/2026)

| Situação | Jogador | Quadra | Repasse |
|---|---|---|---|
| Antes do cutoff | Devolução integral | Não executa a reserva | **Sem repasse** |
| Depois do cutoff, antes do jogo | Sem devolução; perde os tickets | Recebe integral | **Repasse sim** |
| No-show | Sem devolução; perde os tickets | Recebe integral | **Repasse sim** |
| Quadra cancela | Devolução integral | Falha da quadra | **Sem repasse** |
| Contestação aberta | — | — | **Congelado até a decisão** |

- Não existe reembolso parcial: o rateio é integral por jogador e o valor da
  quadra é sempre integral quando há jogo.
- Depois do cutoff, a vaga é oferecida a substituto e a substituição segue a
  ADR 0039; não estornar o desistente.
- Antes do cutoff, o desistente também recebe; a substituição serve para a
  quadra não perder a venda.

## E-mail do pagador e cobrança Pix (Bloco A)

O Mercado Pago exige e-mail do pagador. O app consulta e atualiza o e-mail da conta:

```http
GET /api/v1/me/email
PUT /api/v1/me/email
Authorization: Bearer <access_token>
```

Resposta: `{"email": "pagador@example.com"}` ou `{"email": null}`.

- O backend normaliza para minúsculas e remove espaços; `null` limpa o e-mail.
- E-mail inválido responde `422 validation_error` com `fields`.
- Antes de abrir cobrança Pix, o app deve garantir e-mail preenchido.
- Sem e-mail com o Mercado Pago, a abertura responde `422 payer_email_required`.
- O e-mail é copiado para `booking_payments.payer_email` e
  `purchase_payments.payer_email` como snapshot auditável.
- A visão de pagamento (reserva e compra/passe) expõe `provider`,
  `provider_status`, `status_detail`, `qr_code`, `qr_code_base64`,
  `ticket_url`, `expires_at`, `amount_cents` e `external_reference`.
- `external_reference` é o ID interno da cobrança na reserva e
  `kind:reference_id` na compra/passe; é o mesmo valor enviado ao PSP.

## 11. Login por e-mail e senha (ADR 0050) — contrato v2026-11-19

**Status:** backend implementado em 2026-11-19. O login usa **e-mail + senha**.
O código de 6 dígitos existe apenas para verificar o e-mail no cadastro, trocar
o e-mail e redefinir a senha. O login por código foi removido do contrato. O
caminho de telefone continua existindo e fica dormente por flag.

### 11.1 Flags que o app e o painel devem ler

O backend falha no boot em combinação inválida. O perfil é definido no
ambiente/build; o app não deve presumir flags a partir de dados do usuário.
Rotas desligadas respondem `503` com código estável, e cadastro fechado
responde `403 signup_closed`.

| Flag | Beta | Lançamento | Efeito no cliente |
|---|---|---|---|
| `JOGA_AUTH_EMAIL_ENABLED` | `true` | `true` | Rotas `/auth/email/*`, `/auth/emails` e `/me/account/email*` disponíveis |
| `JOGA_AUTH_PHONE_ENABLED` | `false` | `true` | Rotas de telefone disponíveis (senão `503 phone_auth_disabled`) |
| `JOGA_ALLOW_EMAIL_REGISTRATION` | `true` | `true` | Cadastro por e-mail aberto |
| `JOGA_ALLOW_PHONE_REGISTRATION` | `false` | `true` | Cadastro por telefone aberto |
| `JOGA_PHONE_REQUIRED_FOR_BOOKING` | `false` | `true` | Criar reserva exige telefone verificado |
| `JOGA_SIGNUP_MODE` | `open` | `open` | `closed` bloqueia cadastro público (kill switch) |

No beta, o app deve esconder a entrada por telefone e mostrar e-mail + senha.
No lançamento, deve mostrar telefone como obrigatório e manter e-mail + senha
para login/recuperação.

### 11.2 Cadastro (código verifica o e-mail; senha é definida aqui)

```http
POST /api/v1/auth/email/code
Content-Type: application/json

{"email":"jogador@example.com","purpose":"registration"}
```

Resposta `202`:

```json
{
  "challenge_id": "uuid",
  "expires_at": "2026-11-19T12:10:00Z",
  "resend_after_seconds": 60
}
```

- `purpose`: `registration` ou `password_reset` (não existe mais `login`).
- `202` significa **enfileirado**, não entregue. A entrega roda em workflow a
  cada 5 min; em condições normais o código chega nesse intervalo.
- A resposta é idêntica para e-mail existente e inexistente.

```http
POST /api/v1/auth/email/verify

{"challenge_id":"uuid","code":"123456"}
```

Resposta `200` com `challenge_id`, `purpose`, `verified_at` e
`receipt_expires_at`. O recibo é curto, de uso único e não é token de sessão.

```http
POST /api/v1/auth/email/register

{
  "challenge_id": "uuid",
  "email": "jogador@example.com",
  "password": "uma frase longa e fácil de lembrar",
  "display_name": "Jogador",
  "device_name": "Moto G",
  "platform": "android"
}
```

Resposta `201` = `TokenResponse` (`access_token`, `refresh_token`,
`access_expires_at`, `refresh_expires_at`, `user`). O recibo é consumido uma
única vez; repetir responde `400 invalid_receipt`.

- Senha fora da política responde `400 weak_password` (o código **não** é
  consumido, permitindo corrigir e reenviar).
- `409 email_already_registered` só é devolvido depois que o cliente provou
  controle do endereço (código verificado).
- `429 rate_limited` quando o limite diário de cadastros por IP é atingido.
- `403 signup_closed`/`403 email_registration_disabled` quando o cadastro está
  fechado.

### 11.3 Login por senha (sem código, sem challenge)

```http
POST /api/v1/auth/email/login

{
  "email": "jogador@example.com",
  "password": "uma frase longa e fácil de lembrar",
  "device_name": "Moto G",
  "platform": "android"
}
```

Resposta `200` = `TokenResponse`. Erros:

- `401 invalid_credentials` para e-mail inexistente, senha errada, conta
  suspensa, credencial não verificada ou senha não definida. A resposta é
  **idêntica** em todos os casos; não inferir existência de conta.
- `429 rate_limited` com `Retry-After` (10 tentativas/15 min por e-mail e
  30/15 min por IP).
- `400 invalid_email` para formato inválido.

O login **não** aceita `challenge_id` e **não** existe mais rota de login por
código. `401 invalid_email_login` sai do contrato.

### 11.4 Redefinição de senha

```http
POST /api/v1/auth/email/code

{"email":"jogador@example.com","purpose":"password_reset"}
```

O código usa os mesmos limites, cooldown e fila. A resposta é sempre `202`
para e-mail existente ou não.

```http
POST /api/v1/auth/email/password/reset

{
  "challenge_id": "uuid",
  "email": "jogador@example.com",
  "new_password": "outra frase longa e fácil de lembrar"
}
```

Resposta `200`:

```json
{"status": "ok"}
```

- Código de uso único, TTL curto e invalidação após uso.
- `400 weak_password` para senha fora da política.
- `400 invalid_password_reset` para código/recibo/e-mail/conta inválidos.
- Revoga **todas** as sessões.
- Envia aviso `password_changed` ao e-mail.
- Não reativa conta suspensa.

### 11.5 Troca de senha autenticada

```http
POST /api/v1/me/password
Authorization: Bearer <access_token>

{
  "current_password": "senha atual",
  "new_password": "nova frase longa e fácil de lembrar"
}
```

Resposta `204`. Revoga as **outras** sessões e mantém a atual. Erros:
`401 invalid_credentials` (senha atual errada), `400 weak_password`.

### 11.6 Credencial e troca de e-mail

```http
GET /api/v1/auth/emails
Authorization: Bearer <access_token>
```

Devolve apenas as credenciais da própria conta, sem qualquer detalhe de senha:

```json
{
  "emails": [
    {
      "email": "jogador@example.com",
      "is_primary": true,
      "verified_at": "2026-11-19T12:00:00Z",
      "created_at": "2026-11-19T12:00:00Z"
    }
  ]
}
```

```http
POST /api/v1/me/account/email/challenges
Authorization: Bearer <access_token>

{"new_email":"novo@example.com"}
```

Resposta `202` com `challenge_id`, `expires_at` e `resend_after_seconds`. O
código vai para o **endereço novo**.

```http
PATCH /api/v1/me/account/email
Authorization: Bearer <access_token>

{
  "new_email": "novo@example.com",
  "challenge_id": "uuid",
  "code": "123456"
}
```

Resposta `200` com `email`, `is_primary`, `verified_at` e `created_at`.

- Exige código correto no endereço novo.
- Um aviso é enviado ao endereço antigo.
- O endereço antigo nunca mais autentica (nem com a senha antiga).
- As outras sessões são revogadas; a sessão atual continua válida.
- Nova troca só após 24 h: `429 email_change_cooldown` com `Retry-After`.
- Endereço igual: `400 email_unchanged`.
- Endereço usado por outra conta: `409 email_already_registered`.
- Recibo/código inválido: `400 invalid_email_change`.

**Atenção:** `GET/PUT /api/v1/me/email` continuam sendo o e-mail legado do
pagador (`users.email`). Não são credencial de login e **não alteram a
credencial**. A credencial de login é `GET /api/v1/auth/emails` e a troca é
`PATCH /api/v1/me/account/email`. Não existe alias: um caminho, um significado.

### 11.7 Painel web

```http
POST /api/v1/auth/web/email/registration

{
  "challenge_id": "uuid",
  "email": "operador@example.com",
  "password": "uma frase longa e fácil de lembrar",
  "display_name": "Operador",
  "device_name": "Painel"
}
```

```http
POST /api/v1/auth/web/email/login

{
  "email": "operador@example.com",
  "password": "uma frase longa e fácil de lembrar",
  "device_name": "Painel"
}
```

Resposta = `WebSessionResponse` (`access_token`, `access_expires_at`,
`csrf_token`, `user`, `capabilities`) e cookies `joga_web_refresh` (HttpOnly) e
`joga_web_csrf`. O restante do contrato web (`/auth/web/refresh`,
`/auth/web/logout`, CSRF) não muda. Login errado responde
`401 invalid_credentials`; rate limit responde `429 rate_limited`.

### 11.8 Códigos de erro estáveis

| HTTP | `detail.code` | Quando |
|---|---|---|
| `400` | `invalid_email` | Formato/domínio inválido |
| `400` | `email_domain_not_allowed` | Domínio descartável bloqueado |
| `400` | `invalid_code_or_challenge` | Código/desafio inválido, expirado ou reutilizado |
| `400` | `invalid_receipt` | Recibo inválido, expirado, reutilizado ou de outro endereço |
| `400` | `weak_password` | Senha fora da política |
| `400` | `invalid_password_reset` | Reset inválido (código, recibo, e-mail ou conta) |
| `400` | `invalid_email_change` | Falha genérica de troca de e-mail |
| `400` | `email_unchanged` | Novo endereço igual ao atual |
| `401` | `invalid_credentials` | Login/troca de senha com credenciais inválidas |
| `403` | `signup_closed` | Kill switch de cadastro |
| `403` | `email_registration_disabled` | Cadastro por e-mail desligado |
| `403` | `phone_registration_disabled` | Cadastro por telefone desligado |
| `403` | `phone_required` | Reserva exige telefone verificado (lançamento) |
| `409` | `email_already_registered` | Endereço já vinculado a outra conta ativa |
| `429` | `rate_limited` | Cooldown/limite por endereço, IP ou login |
| `429` | `email_change_cooldown` | Troca recente; aguardar 24 h |
| `503` | `email_auth_disabled` | Credencial de e-mail desligada |
| `503` | `phone_auth_disabled` | Credencial de telefone desligada |

### 11.9 Handoff mobile

- Substituir a tela de telefone por e-mail + senha quando
  `AUTH_PHONE_ENABLED=false`.
- Fluxo de cadastro: e-mail → código (`registration`) → `verify` → criar senha
  no `register`.
- Fluxo de login: e-mail + senha em `POST /auth/email/login`; **não** pedir
  código.
- Fluxo “esqueci minha senha”: `POST /auth/email/code` com
  `purpose=password_reset` → `verify` → `POST /auth/email/password/reset`.
- Troca de senha autenticada: `POST /me/password`.
- Troca de credencial: `POST /me/account/email/challenges` e
  `PATCH /me/account/email`. **Nunca** use `PUT /me/email`: esse caminho é o
  e-mail do pagador e não altera a credencial de login.
- Reutilizar Keychain/Keystore e a rotação de refresh existentes.
- Tratar `503` de telefone como credencial indisponível, não como erro fatal.
- Passkey continua disponível depois do primeiro login e **não pede senha**.
  `email` em `POST /auth/passkeys/authentication/options` é dica opcional e não
  filtra credenciais antes da assinatura.
- Não diferenciar erro de login: mostre a mesma mensagem para
  `invalid_credentials`.
- Enquanto `202` do código estiver pendente, mostre “código enviado”; a entrega
  pode levar até o próximo ciclo do workflow.

### 11.10 Handoff painel web

- Trocar a tela de login/cadastro por telefone pelo fluxo e-mail + senha:
  - cadastro: `/auth/email/code` (`registration`) → `/auth/email/verify` →
    `/auth/web/email/registration` com `password`;
  - login: `/auth/web/email/login` com `email` + `password`;
  - recuperação: `/auth/email/code` (`password_reset`) → `verify` →
    `/auth/email/password/reset`.
- Manter cookies/CSRF atuais (`joga_web_refresh`, `joga_web_csrf`).
- `GET/PUT /me/email` do pagador continua separado e não autentica; a
  credencial usa `/me/account/email`.
- Login errado responde `401 invalid_credentials`; não exibir “e-mail não
  cadastrado”.

## 12. Política de senha e rate limit (ADR 0050)

- Senha: mínimo **10** e máximo **128** caracteres; passphrase permitida; sem
  exigência de símbolo/maiúscula e sem rotação periódica obrigatória.
- Bloqueio de senhas comuns (lista local) e de senha igual ao e-mail/nome
  local; senha fora da política responde `400 weak_password`.
- Hash: Argon2id, `memory_cost=65536` (64 MiB), `time_cost=3`,
  `parallelism=4`; a string PHC completa é armazenada. Nunca retornar hash,
  `password_changed_at` ou qualquer detalhe de senha.
- Login: 10 tentativas/15 min por e-mail e 30/15 min por IP, com `Retry-After`;
  erro sempre `401 invalid_credentials` e custo de verificação equalizado com
  hash descartável para e-mail inexistente.
- O código de e-mail não autentica: só verifica endereço no cadastro e
  redefine senha. Não há flag para reativar login por código.
- Passkey continua preferencial e não exige senha. Telefone segue dormente por
  flag até o lançamento.

## 13. Identidade visual por ícones (v2026-11-20)

A identidade do jogador é um catálogo fechado de seis slots. Não existe texto
livre, upload, URL ou avatar configurável. Toda chave é validada no servidor
contra item ativo do tipo correto e contra desbloqueio.

Slots: `icon_key`, `frame_key`, `accent_key`, `entry_key`, `emote_key`,
`badge_key`.

```http
GET /api/v1/catalog/visual
```

```json
{
  "catalog_version": 1,
  "items": [
    {
      "key": "icon-sport-futebol-5x5",
      "kind": "icon",
      "name": "Futebol 5x5",
      "asset_ref": "icons/icon-sport-futebol-5x5.svg",
      "season": null,
      "unlock_state": "free"
    }
  ]
}
```

- `kind`: `icon|frame|accent|entry|emote|badge`.
- `unlock_state`: `free|xp|pass`.
- `asset_ref` é referência interna de asset; o app nunca recebe URL arbitrária.

```http
GET /api/v1/me/visual
Authorization: Bearer <access_token>
```

```json
{
  "user_id": "uuid",
  "icon_key": "icon-sport-futebol-5x5",
  "frame_key": "frame-bronze",
  "accent_key": "accent-lime",
  "entry_key": "entry-invite-lobby",
  "emote_key": "emote-joinha",
  "badge_key": "badge-beta",
  "catalog_version": 1
}
```

Sem escolha gravada, a resposta usa o baseline `free` do catálogo. `PUT /api/v1/me/visual`
substitui os seis slots e exige todos eles:

```json
{
  "icon_key": "icon-sport-volei-6x6",
  "frame_key": "frame-bronze",
  "accent_key": "accent-azul",
  "entry_key": "entry-invite-lobby",
  "emote_key": "emote-joinha",
  "badge_key": "badge-beta"
}
```

- `400 invalid_visual_item`: chave inexistente, inativa ou de outro tipo.
- `400 visual_item_locked`: item válido de XP/passe ainda não desbloqueado.
- `401 invalid_token`: sem sessão.

**Exposição pública mínima:** lobby, participantes e perfil de terceiro só
podem receber `icon_key`, `frame_key`, `accent_key` e `badge_key`. Nunca
`entry_key`/`emote_key` privados, nome, e-mail, telefone, CPF ou qualquer PII.
O backend centraliza essa projeção; `MatchParticipantResponse.visual` já segue
esse formato.

## 14. Catálogo público de esportes

```http
GET /api/v1/catalog/sports
```

Resposta:

```json
{
  "sports": [
    {
      "id": "uuid",
      "slug": "futebol",
      "name": "Futebol",
      "icon_key": "icon-sport-futebol-5x5",
      "sort_order": 10,
      "active": true,
      "formats": [
        {
          "id": "uuid",
          "slug": "futebol-5x5",
          "name": "Futebol 5x5",
          "team_size": 5,
          "players_per_team": 5,
          "total_participants": 10,
          "duration_minutes": 60,
          "period_count": 1,
          "score_model": "sets_points",
          "positions": [],
          "active": true,
          "version": 1
        }
      ]
    }
  ]
}
```

- Somente esportes `active=true` com ao menos um formato `active=true` aparecem.
- `team_size` é o tamanho de cada equipe; `players_per_team` é o mesmo valor
  exposto explicitamente para o app.
- `score_model`: `sets_points|goals`.
- `positions`: lista de posições; pode ser vazia.
- `GET /api/v1/sports` continua disponível por compatibilidade com o mesmo
  catálogo ativo.

## 15. Administração de esportes (`platform.admin`)

Todas as rotas exigem Allowlist `JOGA_PLATFORM_ADMINS` (user IDs) e respondem
`403 forbidden` para jogador, OWNER ou OPERATOR de organização. Sem token:
`401 invalid_token`.

```http
GET   /api/v1/admin/sports
POST  /api/v1/admin/sports
PATCH /api/v1/admin/sports/{slug}
POST  /api/v1/admin/sports/{slug}/activate
POST  /api/v1/admin/sports/{slug}/deactivate
```

Criação (transacional; o esporte nasce **inativo**):

```json
{
  "slug": "futevolei",
  "name": "Futevôlei",
  "icon_key": "icon-sport-futevolei-3x3",
  "sort_order": 30,
  "formats": [
    {
      "slug": "futevolei-3x3",
      "name": "Futevôlei 3x3",
      "team_size": 3,
      "players_per_team": 3,
      "duration_minutes": 45,
      "period_count": 1,
      "score_model": "sets_points",
      "positions": []
    }
  ],
  "reason": "abertura do catálogo"
}
```

- `409 sport_slug_conflict`: slug já existe.
- `400 invalid_sport`: dados/formatos inválidos.
- `400 invalid_sport_icon`: `icon_key` não é ícone ativo do catálogo visual.
- `409 sport_not_publishable`: ativação sem formato ativo ou sem preço
  configurado em todas as faixas.
- Desativar não apaga formatos, preços, reservas nem histórico; apenas remove o
  esporte do catálogo público.

Seed de exemplo: `futevolei` 3x3 (`team_size=3`, `positions=[]`,
`score_model=sets_points`) nasce **inativo**.

## 16. Preço sugerido e override de tabela

```http
GET /api/v1/admin/pricing/suggest?team_size=5
GET /api/v1/admin/pricing/suggest?team_size=4&mode=contingency
```

Fórmula vigente para cada uma das 6 faixas:

```text
k = ceil(1,2 * teto_cents / (2 * team_size * 310))
```

- `team_size` em `{3,5,6}` usa `standard` por padrão (com 20%).
- Fora de `{3,5,6}`, o modo é obrigatório e explícito: `standard` (com 20%) ou
  `contingency` (sem 20%). O backend não infere.
- Resposta inclui `mode`, `calibration_cents: 310`, `tickets`, `player_price_cents`
  (`tickets * 310`) e `invariant_ok`.
- Invariante verificado: `k*310 >= 1,2*V/(2*team_size)` no modo padrão e
  `k*310 >= V/(2*team_size)` na contingência.

Override:

```http
PUT /api/v1/admin/pricing/band-tickets
```

```json
{
  "band_code": "economica_dia",
  "team_size": 4,
  "tickets": 5,
  "mode": "contingency",
  "reason": "quadra 4x4 de contingência"
}
```

- `reason` é obrigatório.
- `409 ticket_floor_violation`: valor abaixo do piso ou que quebra o invariante.
- `422 pricing_mode_required`: formato fora de 3/5/6 sem escolha explícita.
- `404 band_not_found`: faixa ativa inexistente.
- O override é auditado em `audit_logs` e não altera faixas históricas já
  congeladas em reservas.

## 17. Administração de usuários (`platform.admin`)

Toda escrita exige `reason` e gera evento append-only em `audit_logs`. O admin
nunca lê senha, hash, token, OTP ou CPF em claro e não altera MMR, ledger,
tickets ou resultado.

```http
GET   /api/v1/admin/users?q=&status=&page=1&page_size=20
GET   /api/v1/admin/users/{id}
POST  /api/v1/admin/users
PATCH /api/v1/admin/users/{id}/email
POST  /api/v1/admin/users/{id}/password-reset
POST  /api/v1/admin/users/{id}/suspend
POST  /api/v1/admin/users/{id}/reactivate
POST  /api/v1/admin/users/{id}/sessions/revoke
GET   /api/v1/admin/users/{id}/audit
```

Detalhe do usuário (CPF mascarado; nenhum segredo):

```json
{
  "id": "uuid",
  "status": "active",
  "email": "jogador@exemplo.com",
  "display_name": "Jogador",
  "email_verified": true,
  "cpf_masked": "***.***.***-99",
  "suspended_until": null,
  "created_at": "2026-11-20T12:00:00Z"
}
```

- `POST /admin/users`: `email`, `password`, `display_name?`,
  `verify_email` (opcional, auditado) e `reason`.
- `PATCH /admin/users/{id}/email`: avisa o endereço antigo e revoga todas as
  sessões.
- `POST /admin/users/{id}/password-reset`: envia código; nunca devolve código,
  hash ou token.
- `suspend`: `reason`, `until?`; revoga sessões.
- `reactivate`: limpa `suspended_until`; não restaura sessões antigas.
- `sessions/revoke`: devolve `{"revoked": n}`.
- `GET /audit`: eventos com `action`, `actor_user_id`, `reason`, `details` e
  `created_at`.
- `422 reason_required`: motivo vazio.
- `409 email_already_registered` / `email_unchanged`.
- `400 weak_password` / `invalid_email`.
- `404 user_not_found`.

Capacidade exposta na sessão do painel: `capabilities` inclui `"platform.admin"`
quando o user ID está em `JOGA_PLATFORM_ADMINS`. Papel de organização não
concede essa capacidade.

## 18. Compra de tickets bloqueada por flag

Flag `JOGA_TICKET_PURCHASE_ENABLED` tem **default `false`**.

Com a flag desligada:

- `POST /api/v1/me/tickets/purchases` → `503 ticket_purchase_disabled`.
- `POST /api/v1/me/tickets/purchases/{id}/sync` → `503 ticket_purchase_disabled`.
- `POST /api/v1/me/tickets/purchases/{id}/confirm` → `503 ticket_purchase_disabled`.
- `GET /api/v1/me/tickets` e `GET /api/v1/me/tickets/packs` continuam `200`.

O bloqueio ocorre antes de qualquer escrita: não cria `ticket_purchases`,
`purchase_payments`, `ledger_entries` nem lotes. Passes e assinaturas não são
afetados por esta flag.

## 19. Edição de formatos de esporte (v2026-11-20)

```http
POST  /api/v1/admin/sports/{slug}/formats
PATCH /api/v1/admin/sports/{slug}/formats/{format_id}
POST  /api/v1/admin/sports/{slug}/formats/{format_id}/activate
POST  /api/v1/admin/sports/{slug}/formats/{format_id}/deactivate
```

- `POST` usa o mesmo corpo de `SportFormatInput` da criação, mais `reason`.
- `PATCH` aceita `name`, `duration_minutes`, `period_count`, `score_model`,
  `positions`, `active` a qualquer momento.
- `team_size` e `players_per_team` só mudam enquanto o formato **não tiver uso**
  (fila, lobby, partida, reserva, rating ou troféu). Com uso, responde
  `409 format_in_use`; a instrução é criar um novo formato e desativar o atual.
- `slug` nunca é editável.
- Toda edição relevante incrementa `sport_formats.version`.
- A resposta administrativa inclui `in_use: bool`; o painel deve habilitar
  `team_size`/`players_per_team` apenas quando `in_use=false`.
- Adicionar/editar `team_size` exige célula de preço em todas as faixas ativas.
  Sem célula: `422 pricing_not_configured`; sugerir com
  `GET /admin/pricing/suggest?team_size=`.
- Publicar formato sem preço válido é proibido.
- Auditoria grava ator, formato, campos antes/depois, motivo, data e
  `ip_hash`; não há exclusão de linha nem reescrita de reserva/partida.
- `reason` é normalizado com `strip`; vazio/apenas espaços responde
  `422 reason_required` em todas as escritas administrativas.
- A visão `GET /admin/sports` inclui formatos ativos e inativos; o catálogo
  público continua mostrando apenas ativos.

## 20. Quadras públicas da plataforma (v2026-11-20)

- Organização seed: slug `joga-publico`, nome “JOGA — Quadras Públicas”
  (config `JOGA_PLATFORM_ORG_SLUG`).
- Não aparece em listagens de estabelecimentos. `platform_admin` opera nela
  sem membership.
- `organization_venues.is_public` distingue a quadra pública no discovery.
- A quadra pública é reservável e **gratuita** (ADR 0055): sem preço de espaço,
  taxa, faixa ou consumo de ticket. A reserva registra `venue_price_cents = 0`,
  `fee_cents = 0` e `total_cents = 0`, com `band_code = null`, e não gera
  lançamento no ledger. **A implementar.**
- Reservas nela funcionam sem chave Pix/CNPJ de repasse, porque o próprio JOGA
  opera a quadra; não há cobrança, receita de quadra pública nem repasse.
- O app deve exibir “Grátis” e não abrir etapa de pagamento; o painel deve exibir
  “Gratuita” e não mostrar faixa, preço, taxa, receita ou repasse. **A
  implementar.**
- Publicar quadra pública com `price_cents` maior que zero deve ser recusado, e
  a ativação de quadra pública não exige faixa de preço. **A implementar.**

Descoberta (aditivo):

```json
{
  "venues": [
    {
      "id": "uuid",
      "organization_id": "uuid",
      "name": "Quadra da Praia",
      "is_public": true,
      "is_free": true,
      "covered": false,
      "spaces_count": 1,
      "min_price_cents": 0
    }
  ]
}
```

`GET /discovery/bookable-venues/{id}` também expõe `is_public`. O campo aditivo
`is_free` e o valor `0` em `min_price_cents` para quadra pública estão **a
implementar** (ADR 0055). Em quadra privada, `min_price_cents` continua sendo o
menor preço publicado.

Administração:

```http
GET   /api/v1/admin/venues?active=&page=1&page_size=20
GET   /api/v1/admin/venues/{id}
GET   /api/v1/admin/venues/{id}/spaces
POST  /api/v1/admin/venues
PATCH /api/v1/admin/venues/{id}
POST  /api/v1/admin/venues/{id}/activate
POST  /api/v1/admin/venues/{id}/deactivate
POST  /api/v1/admin/venues/{id}/spaces
PATCH /api/v1/admin/venues/{id}/spaces/{space_id}
GET   /api/v1/admin/venues/{id}/availability?space_id=
POST  /api/v1/admin/venues/{id}/availability
PATCH /api/v1/admin/venues/{id}/availability/{availability_id}
DELETE /api/v1/admin/venues/{id}/availability/{availability_id}?space_id=&reason=
GET   /api/v1/admin/venues/{id}/business-hours
POST  /api/v1/admin/venues/{id}/business-hours
PATCH /api/v1/admin/venues/{id}/business-hours/{business_hour_id}
DELETE /api/v1/admin/venues/{id}/business-hours/{business_hour_id}?reason=
```

- A lista `GET /admin/venues` e o detalhe `GET /admin/venues/{id}` devolvem
  `spaces_count` (total de espaços) e `active_spaces_count` (somente espaços com
  `status = "active"`). `spaces_count` permanece para compatibilidade.
- `GET /admin/venues/{id}` devolve a quadra com `spaces[]`.
- `GET /admin/venues/{id}/spaces` lista espaços para edição.
- `GET .../availability` exige `?space_id=` (o painel deve enviar o espaço
  selecionado).

- `POST /admin/venues` aceita `name`, `city`, `state`, `address_line`,
  `postal_code`, `latitude`, `longitude`, `is_public` (default `true`) e
  `reason`; nasce `inactive`.
- Com CEP e sem coordenada, o backend geocodifica via BrasilAPI e grava
  `geocoding_source`/`geocoding_precision`.
- `activate` exige nome, cidade/UF, coordenada, ao menos um espaço ativo com
  modalidade e formato, disponibilidade semanal e preço em faixa válida. Em
  quadra pública, não exige faixa: o espaço deve estar com `price_cents = 0` e a
  janela com o mesmo valor. **A implementar** (ADR 0055).
- Sem coordenada: `409 geocoding_required`.
- Sem preço para o `team_size`: `422 pricing_not_configured`, sugerindo os
  valores via `GET /admin/pricing/suggest`.
- Demais pendências operacionais: `409 venue_not_publishable`.
- `deactivate` remove da descoberta e preserva espaços, agenda e histórico.
- Espaço administrativo aceita `name`, `description`, `is_covered`, `sport_id`,
  `format_id`, `price_cents`, `status` e `reason`.
- **Fonte de preço:** `venue_spaces.price_cents` é o preço de **publicação**;
  `venue_availability.price_cents` é o preço efetivo da **reserva**. Em espaço
  público os dois devem ser `0`; publicar ou editar com valor maior que zero
  deve ser recusado. **A implementar** (ADR 0055). Editar o preço do espaço
  sincroniza as janelas existentes; criar/editar janela com preço divergente
  responde `422 invalid_input`, e publicar com divergência responde
  `422 pricing_not_configured`.
- `venue_spaces.format_id` define o formato de publicação; a reserva continua
  usando a modalidade vinculada (`VenueSport`) e a janela de disponibilidade.
  Endpoints antigos de organização ignoram esses campos administrativos.
- Disponibilidade e expediente reutilizam o contrato da organização; toda
  escrita exige `reason` normalizado e grava auditoria append-only com
  `ip_hash`.

## 21. Códigos de erro estáveis (v2026-11-20)

| Código | HTTP | Origem |
|---|---:|---|
| `invalid_visual_item` | 400 | Item inexistente, inativo ou de outro tipo |
| `visual_item_locked` | 400 | Item de XP/passe não desbloqueado |
| `invalid_sport` | 400 | Esporte/formato inválido |
| `invalid_sport_icon` | 400 | Ícone fora do catálogo visual ativo |
| `sport_slug_conflict` | 409 | Slug duplicado |
| `sport_not_publishable` | 409 | Sem formato ativo ou sem preço completo |
| `sport_not_found` | 404 | Slug inexistente |
| `pricing_mode_required` | 422 | Formato fora de 3/5/6 sem modo explícito |
| `invalid_pricing_mode` | 422 | Modo/tamanho inválido |
| `band_not_found` | 404 | Faixa ativa inexistente |
| `ticket_floor_violation` | 409 | Override abaixo do piso/invariante |
| `reason_required` | 422 | Escrita administrativa sem motivo |
| `invalid_user` | 400 | Parâmetros de usuário inválidos |
| `user_not_found` | 404 | Usuário inexistente |
| `email_already_registered` | 409 | E-mail em uso |
| `email_unchanged` | 409 | Novo e-mail igual ao atual |
| `weak_password` | 400 | Senha fora da política |
| `invalid_email` | 400 | Endereço inválido |
| `ticket_purchase_disabled` | 503 | Compra desligada por flag |
| `format_in_use` | 409 | `team_size` imutável por uso histórico |
| `format_not_found` | 404 | Formato inexistente no esporte |
| `format_slug_conflict` | 409 | Slug de formato já usado no esporte |
| `invalid_format` | 400 | Campos de formato inválidos |
| `pricing_not_configured` | 422 | Faixa/célula de preço ausente |
| `venue_not_publishable` | 409 | Quadra sem dados operacionais mínimos |
| `geocoding_required` | 409 | Quadra sem coordenada publicável |
| `geocoding_unavailable` | 503 | Provedor de CEP indisponível |
| `invalid_postal_code` | 400 | CEP inválido |
| `invalid_space` | 400 | Modalidade/formato/preço do espaço inválido |
| `platform_organization_missing` | 503 | Seed da organização da plataforma ausente |
| `forbidden` | 403 | Sem `platform.admin` ou sem vínculo exigido |
| `invalid_token` | 401 | Sessão ausente/expirada/revogada |
| `webhook_disabled` | 404 | Webhook do Mercado Pago recebido no ambiente demo |

`reason` ausente no corpo é `422 validation_error`; `reason` apenas com espaços
é `422 reason_required`.

## 22. Modo demonstração sem PSP (v2026-11-20)

`GET /api/v1/app-config` passa a devolver o campo aditivo `demo_mode`:

```json
{
  "min_supported_version": "1.0.1",
  "latest_version": "1.0.1",
  "update_url": null,
  "version_gate_enabled": true,
  "update_required": false,
  "demo_mode": true
}
```

- `demo_mode` é `true` somente com `JOGA_ENVIRONMENT=demo`; local/teste e
  produção devolvem `false`.
- No demo, o PSP é sempre o simulador e `JOGA_MONEY_MODE=simulated`; nenhuma
  chamada de rede ao Mercado Pago é feita.
- `POST /api/v1/bookings/{id}/payments/simulate` libera apenas participante
  ativo do próprio booking; qualquer outro usuário recebe `404 booking_not_found`
  (mesma resposta do `GET`, para não revelar a existência da reserva).
- `POST /api/v1/me/pass/subscriptions/{id}/confirm` libera apenas o dono da
  assinatura; produção continua `403 confirmation_requires_psp`.
- `POST /api/v1/payments/mercadopago/webhook` responde
  `404 webhook_disabled` e não persiste evento.
- A compra de tickets continua desligada por flag (`503
  ticket_purchase_disabled`) e não há dinheiro real, repasse, custódia ou
  NFS-e no demo.

## 23. Fila de matchmaking com múltiplas entradas (ADR 0057)

A rota real é `/api/v1/matchmaking/queue` (prefixo do módulo). O app atual já
usa esse caminho; não existe alias `/api/v1/queue`.

### 23.1 Substituir a seleção

```http
PUT /api/v1/matchmaking/queue
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "formats": ["<uuid>", "<uuid>"],
  "modes": ["casual", "ranked"],
  "court_preference": "ANY"
}
```

- `formats` e `modes` são listas; o servidor deduplica e cria o produto
  cartesiano `formats × modes` como entradas `waiting`.
- `modes` omitido usa `["casual"]`. `[]` explícito (ou `formats: []`) não cria
  nada.
- `court_preference` (`PUBLIC_ONLY|PRIVATE_ONLY|ANY`) é opcional e sobrescreve a
  preferência do perfil em todas as entradas criadas.
- `level`, `center_lat`, `center_lng` e `radius_km` **não fazem parte do
  contrato**: nível, coordenadas e raio vêm do perfil esportivo e da região
  gravada no servidor. Campos extras no corpo são ignorados; o cliente não
  escolhe nível para fins competitivos nem localização por requisição.
- A operação é **atômica**: valida todos os formatos, perfis, região e restrição
  ranqueada antes de escrever; depois cancela todas as `waiting` do usuário e
  insere as novas na mesma transação. Falha não deixa estado parcial.
- Limites: até 20 formatos e 2 modos (produto máximo de 40 entradas por
  requisição).

Resposta `200`:

```json
{
  "entry": {
    "id": "uuid",
    "format_id": "uuid",
    "mode": "casual",
    "court_preference": "ANY",
    "level": "intermediate",
    "status": "waiting",
    "radius_km": 10,
    "created_at": "2026-11-20T12:00:00Z",
    "expires_at": "2026-11-21T12:00:00Z",
    "lobby": null
  },
  "entries": [
    { "...": "mesma forma de entry, uma por entrada waiting" }
  ]
}
```

### 23.2 Consultar e sair

```http
GET    /api/v1/matchmaking/queue
DELETE /api/v1/matchmaking/queue
```

- `GET` devolve `entries[]` com **todas** as entradas `waiting`, da mais recente
  para a mais antiga. O campo legado `entry` continua sendo a última entrada
  `waiting` **ou** `matched` (com `lobby` preenchido quando pareada).
- `DELETE` cancela **todas** as `waiting` do usuário e responde `204`. Sem
  nenhuma entrada ativa, responde `404 not_queued`.

### 23.3 `POST` legado

`POST /api/v1/matchmaking/queue` com
`{ "format_id", "mode"?, "court_preference"? }` continua funcionando exatamente
como antes (cria uma entrada; `409 already_queued` se já existir a mesma
combinação `waiting`). Ele é o caminho de compatibilidade do app antigo e não
substitui a seleção inteira.

### 23.4 Regras do matcher

- O pool usa **todas** as entradas `waiting`, nunca apenas a mais recente.
- Se duas entradas do mesmo usuário fecham lobby no mesmo ciclo, uma é sorteada
  uniformemente e as demais permanecem `waiting` (não são canceladas).
- O horário já comprometido do usuário vem do **lobby**, não da reserva:
  `origin IN ('matchmaking','manual')`, participante ativo,
  `status != 'cancelled'` e `scheduled_end_at > now`. Lobby cancelado libera o
  horário; lobby de outro usuário não afeta.
- A janela do perfil não é consumida: um lobby 11–12 com janela 10–14 deixa
  10–11 e 12–14 disponíveis para as outras entradas, inclusive entre casual e
  ranqueada.

### 23.5 Erros estáveis

| HTTP | `detail.code` | Quando |
|---:|---|---|
| `400` | `invalid_mode` | Modo fora de `casual`/`ranked` |
| `400` | `invalid_format` | Formato inexistente ou inativo |
| `403` | `ranked_restricted` | Trust Factor restringe a fila ranqueada |
| `409` | `sport_profile_required` | Falta perfil esportivo para algum formato |
| `409` | `region_required` | Falta região para criar entradas |
| `409` | `queue_conflict` | Conflito de concorrência no `PUT`; repetir |
| `409` | `already_queued` | `POST` duplicado para a mesma combinação |
| `404` | `not_queued` | `DELETE` sem entradas `waiting` |

### 23.6 Compatibilidade

- O app antigo continua lendo `entry` e chamando `POST`/`DELETE`.
- O app novo deve usar `PUT` para trocar a seleção e ler `entries`.
- `DELETE` mudou de "cancela uma" para "cancela todas": app antigo com uma única
  entrada não percebe diferença.
- Nenhum campo existente foi removido; `entries` e o `PUT` são aditivos.
