# Fila de tarefas — administração do painel

Atualizado em 2026-11-20. Escopo exclusivamente `web/`.

## Concluído

- [x] Contrato único de usuários: `verify_email`, `reason`, sem
      `skip_verification` e sem `temporary_password`.
- [x] Reset de senha informa apenas o envio do código para o e-mail da conta.
- [x] Auditoria administrativa consome somente `{events: [...]}`.
- [x] Esportes usam `icon_key`, `sort_order`, `period_count`,
      `players_per_team` e `reason`.
- [x] Seletor de ícone consome `GET /catalog/visual`, filtra `kind=icon` e
      `active`, e cai para texto com aviso se o catálogo falhar.
- [x] Edição de formato permanece read-only com aviso explícito; `in_use` é
      exibido quando a API devolve.
- [x] Preço usa `band_code` + `mode`; `mode` é explícito fora de 3x3/5x5/6x6.
- [x] Prévia de `k` por formato novo e bloqueio de `pricing_not_configured`.
- [x] Administração de quadras públicas em `/admin/venues`.

## Decisões registradas

- **Teto de tickets:** 1..1.000, alinhado a
  `backend/app/api/v1/admin.py` (`BandTicketsOverrideRequest.tickets`,
  `ge=1, le=1000`) e à ADR 0049 §13. O texto canônico do erro é
  `Informe um número inteiro de tickets entre 1 e 1.000.`
- **Invariante:** o modo é sempre explícito. `standard` exige 20% sobre o
  teto; `contingency` exige o teto. O texto canônico do erro é
  `Essa quantidade não cobre o preço no modo padrão. O mínimo para 5x5 é 5.`
- **Senha:** o backend não devolve senha temporária. O painel não mantém
  `temporary_password` em tipos, tela, storage ou testes.
- **Auditoria:** sem paginação no backend atual; quando houver, será contrato
  novo.
- **Quadras públicas:** o frontend envia `reason` também nas escritas de
  espaço e agenda para preservar a trilha de auditoria; o backend ignora
  campos extras se não os usar.

## Dependências do backend

- [ ] `PATCH /admin/sports/{slug}/formats/{formatId}` para corrigir
      `team_size`, duração, períodos, `score_model` e posições de esporte já
      publicado.
- [ ] Expor `in_use` em `AdminSportFormat` e bloquear alteração com
      `409 format_in_use`.
- [ ] Expor `pricing_not_configured` na pré-checagem de publicação/preço.
- [ ] Confirmar o contrato de `availability` e `business-hours` das quadras
      públicas (campos e formato do PUT).

## Próximos passos

- [ ] Consumir o contrato de edição de formato quando existir, sem simular.
- [ ] Substituir o fallback textual de ícone por seletor obrigatório quando o
      catálogo visual estiver sempre disponível.
- [ ] Adicionar paginação de auditoria apenas após contrato novo do backend.
