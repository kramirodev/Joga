# Backlog — Mercado Pago, contratos e dívidas de backend

Atualizado em 2026-11-15. Este arquivo separa o Bloco A (Mercado Pago em
produção), o Bloco B (contratos consumidos por app/site) e o Bloco C (backlog
não-PSP). `PLANS.md` continua sendo a fonte de ordem das fases e
`docs/PENDENCIAS.md` o painel consolidado.

## Bloco A — Mercado Pago em produção

Decisão registrada na **ADR 0048**: Mercado Pago Orders API é o PSP do protótipo
com jogadores reais; Inter/Pagar.me ficam para o futuro. Sem split e sem
recebedor automático; repasse continua ledger/manual conforme ADR 0040.

| ID | Tarefa | Estado |
|---|---|---|
| MP-01 | ADR 0048 + atualização de PLANS/PENDENCIAS/THREAT_MODEL/adapter | **Concluído em 2026-11-15** |
| MP-02 | Guardas de configuração de produção (provider, token, segredo, URL HTTPS; sem e-mail global) | **Concluído em 2026-11-15** |
| MP-03 | Validar Orders API real (qr_code, base64, ticket_url, expires_at, status, idempotência) | Pendente — exige credenciais do Mercado Pago |
| MP-04 | E-mail do pagador por usuário, snapshot e `payer_email_required` | **Concluído em 2026-11-15** |
| MP-05 | Webhook real, retry (`attempts`, `last_error`, `next_attempt_at`) e worker | Pendente (P0) — persistência bruta e assinatura já existem |
| MP-06 | Confirmação local dev-only + teste | **Concluído em 2026-11-15** |
| MP-07 | Reembolso real (processing/failed/parcial/idempotência) | Pendente (P1) |
| MP-08 | Conciliação real com o Mercado Pago | Pendente (P1) — exige credenciais |
| MP-09 | Observabilidade e runbook de Pix/webhook/estorno | Pendente (P1) |
| MP-10 | MED/chargeback e bloqueio de liberação | Pendente (P1) |
| MP-11 | Documentar repasse centralizado/manual e ausência de split | Pendente (P1) — documentação parcial na ADR 0048 |

## Bloco B — Contratos para app e site

| ID | Contrato | Estado |
|---|---|---|
| C-01 | Visão de pagamento com provider, status, status_detail, QR, ticket_url, expires_at, amount_cents e external_reference | Pendente de verificação (P0) |
| C-02 | `total` em `NotificationListResponse` (jogador e moderação) | Pendente (P2) |
| C-03 | Convite de membro por telefone (`organization_invitations`) | Pendente (P2) |
| C-04 | T3 por estabelecimento (`booking_t3_minutes`) | Pendente (P2) |
| C-05 | Exportação financeira CSV por organização | Pendente (P2) |
| C-06 | Revisão independente de fotos (fila e decisão) | Pendente (P2) |
| C-07 | Catálogo de avatares e inventário | Pendente (P2) |
| C-08 | Kit da partida no lobby | Pendente (P3) |
| C-09 | Painel B2B de ocupação | Pendente (P3) |

## Bloco C — Backlog não-PSP

| ID | Tarefa | P |
|---|---|---|
| B1 | Mapear HTTP 504 da BrasilAPI para `CepTimeout`/504 e manter 503 como 502 | P2 |
| B2 | `scripts/cleanup_geo.py` com `--dry-run` | P3 |
| B3 | CLI de backfill de CEP por CSV com auditoria/proveniência | P3 |
| B7 | Redirecionamento de quadra em recusa/expiração (se aprovado) | P2 |
| B8 | Limite configurável de substituições | P2 |
| B9 | Janela de contestação financeira (T10) após decisão de prazo | P2 |
| B10 | Conclusão automática da partida ou confirmação obrigatória | P2 |
| B17 | Backfill em massa de lotes legados | P3 |
| B19 | Classificador local/open-source | P2 |
| B20 | Suspensão permanente | P2 |
| B21 | Ajustar `street` vs `approximate` da BrasilAPI | P2 |
| B22 | Fallback ViaCEP/Nominatim/Google | P2 |
| B23 | Provedor pago de geocoding | P3 |
| B24 | Restringir busca por CEP/cidade ao passe | P2 |
| B25 | Reembolso de passe/pacote | P2 |
| B26 | Aviso de 30 dias na reclassificação de faixa | P2 |
| B27 | Regra de arredondamento de 4x4 | P3 |
| B29 | Crédito de estreia | P3 |
| B30 | Destino do valor não reembolsado em desistência | P2 |
| B31 | `p_t` dinâmico por Trust Factor (só com ADR) | P3 |
| B32 | Score de risco de pagamento | P3 |
| B36 | Catálogo definitivo de equipamento | P3 |
| B38 | Data do primeiro evento de marketing | P2 |

## Não é tarefa de backend

Parecer fiscal do ingresso; parecer jurídico de intermediação/custódia/CDC; KYC
contratual do fornecedor; termos de uso e tela de pagamento; retenção
definitiva/LGPD; direito de exclusão; revisão jurídica de suspensão permanente.

## Fora de escopo agora

Inter PJ (adaptador, credenciais, mTLS, conciliação e webhook), Pagar.me,
Fase 18 (Publicidade), `p_t` dinâmico, score de risco e split/recebedor no
Mercado Pago.
