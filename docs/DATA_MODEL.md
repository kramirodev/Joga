# Modelo de dados — JOGA (as-built)

**Versão:** 2.0<br>
**Data:** 16 de novembro de 2026<br>
**Fonte:** migrations Alembic em `backend/migrations/versions/` e modelos SQLAlchemy em `backend/app/modules/`.<br>
**Head de migrations:** `j3f4a5b6c7d8` (cadeia linear, 53 revisões).<br>
**Natureza:** este documento substitui a versão incremental das Fases 3–4. Ele descreve o schema **existente**, não o alvo. O alvo financeiro da ADR 0049 está na Fase 14E.

> **Regra de leitura.** O banco é a fonte da verdade. Este resumo existe para orientar leitura e revisão; a definição exata de colunas, tipos e constraints está nos modelos e migrations. Não usar este documento para `alembic revision --autogenerate`.

---

## 1. Convenções

- UUID como chave primária; telefone nunca é chave primária.
- `timestamptz`/UTC no backend; datas de evento em UTC.
- Valores monetários em centavos inteiros.
- Tabelas de histórico financeiro e competitivo são append-only por convenção; o ledger novo tem trigger de imutabilidade.
- `organization_id` isola dados de estabelecimentos; a autorização é verificada no serviço, não apenas pelo UUID.
- Nomes de constraint seguem a convenção `ck_<tabela>_<nome>` / `uq_<tabela>_<nome>`.

---

## 2. Identidade e sessões

| Tabela | Papel |
|---|---|
| `users` | Identidade central, status, e-mail, `suspended_until` |
| `user_phones` | Telefone protegido, hash de busca, verificação e estado |
| `phone_challenges` | Desafios OTP, hash, tentativas, expiração e recibo |
| `devices` | Dispositivos vinculados e sinais mínimos |
| `passkey_credentials` | Credenciais WebAuthn, contador e revogação |
| `passkey_challenges` | Desafios de registro/autenticação, uso único |
| `sessions` | Access/refresh hashes, família, rotação e revogação |
| `security_events` | Eventos de autenticação e abuso |
| `audit_logs` | Ator, ação, recurso, motivo e timestamp |

**Constraints relevantes:** telefone ativo único por hash; `credential_id` único; refresh hash único; sessão revogada não autentica; conta suspensa só acessa rotas de recurso.

**Lacunas conhecidas:** não há endpoint de recuperação de conta; `ChallengePurpose.recovery` existe no modelo, mas não é aceito pela API. Não há limite por dispositivo em refresh/passkey/WS.

---

## 3. Perfil, catálogo e descoberta

| Tabela | Papel |
|---|---|
| `sports` | Modalidades |
| `sport_formats` | Formatos, duração, composição e versão |
| `user_profiles` | Nome, gênero, cidade e preferências |
| `user_sport_profiles` | Nível autodeclarado e preferência por formato |
| `availabilities` | Janelas de disponibilidade do jogador |
| `user_regions` | Região aproximada e coordenada arredondada |
| `venues` | Locais descobertos, geografia e endereço |
| `postal_code_cache` | Cache de CEP/geocoding com TTL e proveniência |

**Constraints relevantes:** coordenadas validadas; raio máximo; CEP normalizado; cache por CEP+número+versão do provedor.

**Lacunas conhecidas:** não há `user_avatars`; o avatar é decisão de catálogo ainda não implementada. `sport_equipment_requirements` não existe.

---

## 4. Organizações, estabelecimentos e quadras

| Tabela | Papel |
|---|---|
| `organizations` | Estabelecimento/organização, CNPJ, chave Pix e `payout_status` |
| `organization_memberships` | Usuário, papel e vínculo |
| `organization_venues` | Perfil comercial do estabelecimento, endereço, CEP, coordenada e proveniência |
| `venue_spaces` | Quadras/espaços, cobertura e estado |
| `venue_sports` | Vínculo espaço–modalidade |
| `venue_availability` | Janelas semanais, preço e duração |
| `venue_blackouts` | Bloqueios manuais e reservas externas |
| `venue_business_hours` | Expediente e horário comercial |
| `venue_closures` | Fechamentos e feriados |
| `venue_photos` | Fotos, revisão, motivo, storage e retenção |
| `pricing_bands` | Faixas de exibição/preço, versão e teto |
| `pricing_band_tickets` | Conversão tickets ↔ faixa |

**Constraints relevantes:** CNPJ válido; chave Pix tipada; `payout_status` em `pending/active/blocked`; foto só pública após revisão; vínculo `organization_venues.venue_id` único e opcional.

**Lacunas conhecidas:** não existe `venue_payment_accounts`; o repasse é armazenado em `organizations`. Não há ACL por quadra. A tabela de faixas é hoje usada como preço; a ADR 0049 exige que ela seja apenas exibição/conversão, com preço do espaço + taxa persistidos na reserva (Fase 14E).

---

## 5. Reservas, holds e presença

| Tabela | Papel |
|---|---|
| `bookings` | Reserva, estado, preço, faixa, política e timestamps |
| `booking_participants` | Vaga, contribuição, pagamento, `settled_with` e tickets consumidos |
| `booking_holds` | Bloqueio do espaço e expiração |
| `booking_timers` | T1/T2/T3 independentes |
| `booking_events` | Histórico append-only de transições e ações |
| `booking_substitutions` | Substituições e vínculo com a vaga |
| `lobby_substitutes` | Fila de substitutos do lobby |
| `booking_refund_exclusions` | Exclusões de reembolso por desistência |

**Estados de `bookings`:** `PARTICIPANT_CONFIRMATION`, `REQUESTED`, `DECLINED`, `EXPIRED`, `HOLD_CONFIRMED`, `PAYMENT_PENDING`, `CONFIRMED`, `CANCELLED`, `CANCELLED_BY_VENUE`, `CANCELLED_BY_PLAYER`, `SUBSTITUTING`, `COMPLETED`.

**Estados de `booking_participants.payment_status`:** `PENDING`, `PAID`, `REFUNDED`, `FAILED`, `WAIVED`.

**Constraints relevantes:** uma reserva por lobby; vaga ativa única por assento/usuário; timers por tipo; hold ativo único por espaço/intervalo (lógica de serviço); preço não negativo.

**Lacunas conhecidas:** não há `ExclusionConstraint`/`tstzrange` para sobreposição; a proteção é feita no serviço. `booking_participants.payment_status` aceita `EXPIRED`/`CANCELLED` desde `k5b6c7d8e9f0`. `bookings` guarda `venue_price_cents`, `fee_cents`, `fee_percent_applied`, `total_cents` e `pricing_version` desde `m7d8e9f0a1b2`; reservas antigas ficam em `legacy_v0` com taxa zero.

---

## 6. Pagamentos, PSP e ledger

| Tabela | Papel |
|---|---|
| `booking_payments` | Cobrança por participante/versão, status e dados do provedor |
| `purchase_payments` | Compra de pacote/passe, `kind` e `reference_id` |
| `payment_refunds` | Reembolso por cobrança (um por pagamento) |
| `payment_events` | Eventos append-only de cobrança/PSP |
| `psp_webhook_events` | Webhook bruto, idempotência por provedor e retry |
| `booking_ledger_entries` | Ledger legado single-entry por reserva |
| `ticket_ledger` | Ledger append-only de créditos/consumos |
| `ledger_accounts` | Plano de contas do ledger de dupla entrada (ADR 0049) |
| `ledger_transactions` | Transação balanceada e idempotente |
| `ledger_entries` | Lançamentos de débito/crédito, imutáveis por trigger |
| `venue_releases` | Repasse ao fornecedor, status e elegibilidade |
| `financial_disputes` | Contestação do fornecedor |
| `fiscal_documents` | Intenção/documento fiscal por reserva (placeholder) |
| `terms_versions` | Versões de termos e aceite |

**Constraints relevantes:** webhook único por `(provider, event_id)`; reembolso único por pagamento; ledger de dupla entrada balanceado; `VENUE_RELEASE` idempotente; status de pagamento validado.

**Lacunas conhecidas:** o ledger de dupla entrada é escrito pelos fluxos cobertos (Etapas 6/6b). A leitura do saldo usa `JOGA_TICKET_BALANCE_SOURCE` e valida caixa + tickets. `payment_refunds` ainda não permite reembolso parcial. `fiscal_documents` e `terms_versions` não têm chamador. A Etapa 9 (aposentadoria dos ledgers legados) está pendente.

---

## 7. Crédito, carteira, passe e temporada

| Tabela | Papel |
|---|---|
| `ticket_packs` | Escada de pacotes e preço de exibição |
| `ticket_purchases` | Compra de pacote, valor, status e idempotência |
| `ticket_lots` | Lote de origem em tickets; `unit_price_cents` só para abertura/reembolso; `remaining` é o saldo de tickets |
| `ticket_lot_consumptions` | Consumo por lote e referência; `amount` é a contagem de tickets |
| `ticket_balances` | Cache do saldo em tickets, mantido na mesma transação; a leitura valida lotes e caixa com a flag `JOGA_TICKET_BALANCE_SOURCE` |
| `pass_subscriptions` | Assinatura trimestral, status e período |
| `pass_deliveries` | Entrega mensal idempotente por assinatura/mês |
| `seasons` | Temporada trimestral, início/fim e estado |
| `season_progress` | Nível, XP e progresso |
| `xp_events` | Ledger append-only de XP |
| `win_streaks` | Sequência de vitórias por semana |
| `season_items` | Itens da trilha e do catálogo |
| `season_track_levels` | Níveis da trilha e item associado |
| `season_claims` | Resgates de nível |
| `badges` / `player_badges` | Insígnias e atribuições |
| `player_items` | Itens possuídos e equipados |
| `mission_progress` | Missões semanais |
| `season_placements` | Posição/divisão no fechamento |

**Constraints relevantes:** consumo idempotente por `ref_type/ref_id/user`; entrega de passe única por assinatura/mês; XP idempotente por `ref_id`; lote expirado não conta no saldo.

**Lacunas conhecidas:** `season_items.code` é único globalmente, não por temporada; `player_items` é único por `(user, item_code)`, impedindo recompensa por temporada. Não há revogação de item de passe. A fronteira de temporada/semana usa UTC, não o fuso local.

---

## 8. Matchmaking, lobbies, partidas e resultados

| Tabela | Papel |
|---|---|
| `queue_entries` | Fila persistente por formato/modo |
| `lobbies` | Origem, visibilidade, horário, formato e quadra |
| `lobby_participants` | Participantes, capitão e estado |
| `matchmaking_runs` | Execuções do worker e versão do algoritmo |
| `lobby_messages` | Chat do lobby |
| `lobby_invites` | Convites e estado |
| `matches` | Partida e estado |
| `match_participants` | Jogadores, equipes e presença |
| `match_state_transitions` | Histórico de estados |
| `match_result_reports` | Relatos de resultado |
| `match_result_rounds` | Rodadas de votação |
| `match_result_disputes` | Disputas |
| `match_result_evidence` | Evidência textual privada |
| `match_result_reviews` | Revisão humana |
| `match_result_decisions` | Decisão e justificativa |
| `idempotency_records` | Idempotência de operações HTTP |

**Constraints relevantes:** uma entrada ativa por usuário/formato/modo; uma partida por lobby; voto único por participante/rodada; rating uma vez por partida/usuário/versão; evidência limitada a 2.000 caracteres.

**Lacunas conhecidas:** não há `lobby_venue_votes`; a votação de troca de quadra não existe no backend. Não há `match_equipment`/claims. `GET /matches` não pagina. `advance` não usa lock de partida.

---

## 9. Rating, Trust Factor e clãs

| Tabela | Papel |
|---|---|
| `rating_accounts` | Rating interno por usuário/formato |
| `rating_events` | Histórico append-only de rating |
| `trust_accounts` | Score e restrição ranqueada |
| `trust_events` | Eventos de confiabilidade |
| `clans` | Clã, visibilidade e dono |
| `clan_members` | Membros, papéis, vínculo e carência |
| `clan_join_requests` | Pedidos de entrada |
| `clan_messages` | Chat do clã |
| `clan_reports` | Denúncias de mensagem |
| `clan_trophy_events` | Pontuação de troféus |
| `clan_trophy_snapshots` | Snapshot no fechamento da temporada |

**Constraints relevantes:** um vínculo ativo por clã; troféus ligados a partida/temporada; rating imutável por partida/versão.

**Lacunas conhecidas:** o código atribui troféus a partidas finalizadas, incluindo casuais (ADR 0046), mas o documento técnico dizia “somente ranqueadas”; a decisão vigente é a ADR 0046.

---

## 10. Social, notificações e moderação

| Tabela | Papel |
|---|---|
| `friendships` | Solicitações, aceite e vínculo |
| `user_blocks` | Bloqueios entre usuários |
| `notifications` | Central persistida, canal e leitura |
| `device_push_tokens` | Tokens de push por dispositivo |
| `outbox_events` | Eventos transacionais pendentes |
| `rate_limit_counters` | Contadores de janela fixa |
| `moderation_reports` | Denúncia de perfil e contexto |
| `moderation_actions` | Medidas, justificativa, prazo e recurso |
| `moderation_appeals` | Recursos e decisão |
| `moderation_operators` | Operadores e papel ADMIN |

**Constraints relevantes:** notificação única por chave; operador por usuário; report com contexto limitado; medida temporária de 1–30 dias.

**Lacunas conhecidas:** não há `chat_rooms`/`chat_memberships`; o chat usa `lobby_messages`/`clan_messages`. Não há busca de usuário para amizade. `create_report` e `NotificationService.create` são select-then-insert. Revogar uma medida limpa a suspensão global.

---

## 11. Constraints críticas e invariantes

1. Telefone ativo único por hash protegido.
2. `credential_id` de passkey único; refresh hash único.
3. Um membro ativo por organização; um vínculo ativo por clã.
4. Foto de quadra só pública após revisão e organização ativa.
5. Vaga ativa única por reserva/assento e por reserva/usuário.
6. Um timer por tipo/reserva; hold ativo único por espaço/intervalo.
7. Reserva só confirma com todas as vagas quitadas (crédito ou Pix).
8. Webhook único por provedor/evento; reembolso único por pagamento (limitação atual).
9. Rating uma vez por partida/usuário/versão; MMR bruto nunca exposto.
10. Resultado em disputa não gera rating.
11. Denúncia só por participante do lobby e com mensagens da própria conversa.
12. Ledger de dupla entrada balanceado e imutável (quando integrado).

---

## 12. Lacunas que a Fase 14E deve fechar

- ~~`bookings.venue_price_cents`, `fee_cents`, `fee_percent_applied`, `total_cents`~~ — **feito em `m7d8e9f0a1b2`**, com `pricing_version` e backfill `legacy_v0`.
- Sombra de escrita do `ledger_*` nos fluxos de compra, confirmação de reserva, devolução, repasse, passe e vagas por passe/grátis/admin — **feita nas Etapas 6/6b** (`n8e9f0a1b2c3`, `o9f0a1b2c3d4`, `p0a1b2c3d4e5` + `ledger/flow.py`). A leitura pública usa `JOGA_TICKET_BALANCE_SOURCE` (`cache`/`ledger`); em `ledger`, conta ausente ou divergência falha alto.
- Migração de saldo monetário legado — **feita na Etapa 6**: abertura `Σ remaining × unit_price_cents` contra `opening_equity`. Os lotes continuam em tickets; não existe `remaining_cents`. Passe, grátis e admin ficam fora da abertura.
- ~~`credit` sem expiração; passe com `period`, não `expires_at`~~ — **feito em `m7d8e9f0a1b2`**: comprado não expira, passe usa `period` mensal e ingresso de nível expira com a temporada.
- `booking_participants.space_charge_cents`/`fee_charge_cents`/`funding_source` e `ticket_lot_consumptions.amount_cents` — **feitos na Etapa 6**; `ticket_lots` guarda tickets e `unit_price_cents` (só abertura/reembolso). A tabela 2D é a unidade de consumo.
- CPF cifrado e documento fiscal por reserva.
- Reembolso parcial.
- Constraint de exclusão para sobreposição de reservas.
- Unicidade de item de temporada por temporada.
- ~~Correção da constraint de `payment_status` para aceitar os estados escritos pelo serviço~~ — **feito em `k5b6c7d8e9f0`**.

---

## 13. Migrations de referência

- Identidade: `3c9d51a7e2b4`, `d4a7f2c9e610`, `a7c3e9f2b415`.
- Perfil/descoberta: `b8d2f4a6c910`, `c5d6e7f8a9b0`.
- Organizações/quadras: `a1b2c3d4e5f6`, `99c1055b81b5`, `a1c2e3f40517`, `e1f2a3b4c5d6`, `f5a6172b3949`.
- Reservas/pagamentos: `26b70fd0fbc7`, `c97807d1b140`, `bb4083b7b697`, `c15a1b2c3d4e`, `f4b5c6d7e8f9`, `e4a1c9d7b203`.
- Crédito/temporada: `d3e4f5061927`, `e4f5061a2838`, `c9f0a1b2d3e4`, `b7c8394d5162`, `c8d94a5e6273`, `d9e95b6f7384`, `f5b2d8e4c310`.
- Ledger/fiscal/legal: `j3f4a5b6c7d8`, `i2e3f4a5b6c7`.

O head atual é `j3f4a5b6c7d8`. A validação de `alembic upgrade head`, `downgrade base` e `alembic check` deve ser feita com PostgreSQL real antes de declarar o schema estável.
