# Fase 17C — Contratos de backend para app e site

**Status:** implementado em 2026-11-15.
**Depende de:** Fase 17A/17B/17C (moderação), Fases 13 (reservas), 15 (financeiro), 11 (auditoria).
**Não inclui:** convite de membro por telefone, IA paga, alterações em `mobile/` ou `web/`.

## App mobile

### Conta suspensa

- `POST /api/v1/auth/refresh` de conta suspensa responde
  `401 {"detail":{"code":"account_suspended"}}`.
- Refresh inválido/expirado continua `400/401 invalid_refresh_token`.
- `GET /api/v1/auth/me` e as demais rotas comuns continuam `401 invalid_token`.
- `GET /api/v1/moderation/actions/me` e
  `POST /api/v1/moderation/actions/{action_id}/appeal` aceitam a sessão
  suspensa para o jogador ver e contestar a própria medida.
- `SessionService.authenticate(require_active=False)` é usado apenas nessas
  duas rotas; o padrão continua exigindo conta ativa.
- Contestar a medida de outro usuário retorna `404 not_found`.

## Site / painel

### Reservas

- `GET /api/v1/bookings` e `GET /api/v1/organizations/{id}/bookings` aceitam
  `status`, `from`, `to`, `limit` (1–100, default 50) e `offset`.
- `from` é inclusivo, `to` é exclusivo e ambos precisam de fuso (`Z` ou offset).
- O envelope passa a ser `{bookings, total, limit, offset}`.
- `BookingView.timezone` devolve o fuso IANA do estabelecimento; `starts_at` e
  `ends_at` continuam em UTC.
- Período sem fuso, invertido ou vazio retorna `422 invalid_time_range`.

### Erros de validação

Erros Pydantic passam a usar:

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

O valor enviado não é ecoado.

### Capacidades da sessão web

`POST /api/v1/auth/web/registration`, `/login` e `/refresh` incluem
`capabilities`:

- conta comum: `[]`;
- `MODERATOR`: `["moderation.read"]`;
- `ADMIN`: `["moderation.read", "moderation.manage"]`.

O site deve usar `capabilities` para esconder o link de moderação e não provocar
`403` em `/moderation/me` para conta comum.

### Totais

Passam a devolver `total` (antes da paginação):

- `GET /organizations/{id}/financial/receivables`
- `GET /organizations/{id}/financial/statement`
- `GET /organizations/{id}/financial/disputes`
- `GET /organizations/{id}/audit`

## Fora desta fatia

- Convite de membro por telefone/e-mail/QR: exige tabela de convite, token,
  consentimento, aceite, expiração, notificação e auditoria. Tratar como fatia
  própria com ADR.
- Classificador local/open-source e suspensão permanente.

## Verificação

- Backend: `ruff check`, `ruff format --check`, `mypy app`.
- Suíte completa: **477 passed, 29 skipped** (2026-11-15).
- Testes novos: refresh de conta suspensa, recurso de terceiro, paginação e
  filtros de reservas, `timezone`, `total` financeiro/auditoria, shape 422 e
  `capabilities` da sessão web.
