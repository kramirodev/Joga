# Pendências abertas do JOGA

**Atualizado em:** 16 de novembro de 2026

Backlog detalhado do Mercado Pago e dos contratos: `docs/BACKLOG_MERCADO_PAGO_E_CONTRATOS.md`.
Pendências jurídicas, fiscais e regulatórias: `docs/JURIDICO_PENDENCIAS.md`.

Este arquivo consolida o que ficou aberto após as Fases 11–17, com a 14D como protótipo, a 15 como proposta técnica local e a 14E como transição obrigatória da ADR 0049. Não substitui `PLANS.md`, os ADRs nem os arquivos de fase; serve como painel de acompanhamento.

## Bloqueios externos

| Pendência | Fase | Impacto | Próximo passo |
|---|---|---|---|
| Mercado Pago no protótipo | 14 | PSP do protótipo com jogadores reais (ADR 0048); validação live, reembolso real e conciliação pendentes | Fase 14B; credenciais e webhook público |
| KYC contratual do fornecedor | 12B/14B | Reserva paga não pode abrir sem chave de repasse validada; o KYC do modelo C é da fase comercial | Decidir contrato e onboarding; escrow na 19A |
| SMS real | 10/19 | Login real depende de OTP | Escolher provedor, custo, antiabuso e LGPD |
| Push real | 10/19 | Notificações de prazo e resultado | Configurar APNs/FCM e credenciais |
| Central de notificações | 9D/17C | **Implementada** no app e no painel; backend separa canais | Testar leitura e push real |
| Mapas | 10/19 | Camada visual de descoberta | Pode esperar; usar lista/distância no início |
| CNPJ/MEI e revisão jurídica | 14B/19 | Dinheiro real e contratos | Definir entidade, contador e parecer jurídico |
| Storage de fotos de produção | 12A/19 | Fotos privadas e retenção | Escolher storage, criptografia e backup |

## Pendências de produto e engenharia

| Pendência | Fase | Estado |
|---|---|---|
| T2 em horário comercial | 13E/14B | **Implementado** com expediente, feriados e fechamentos; falta validar casos de borda |
| T2 máximo de 60 min | 13B/14B | **Implementado** em 2026-11-09 (ADR 0039) |
| T3 configurável por estabelecimento | 13B/14B | Hoje usa configuração global |
| Política consolidada de cancelamento, substituição e ausência | 14B/15 | **Definida na ADR 0039**, que supera a ADR 0038; fatias 1–6 implementadas no backend |
| Fila de substitutos e timers T4–T9 | 13B/15 | Fatias 1–6 implementadas (fila, chamada automática, T4/T5, cancelamento, expiração, atribuição/pagamento, paid seat e presença T6–T9) |
| Adaptação de formato (4x4 + rodízio) | 13B/15 | **Recomendação automática implementada** (`players_per_team`/`formation_note`); rodízio controlado não existe |
| Vaga paga em no-show | 15 | **Implementada**: substituto `WAIVED`/`covered_by_payment_id`, sem nova cobrança |
| Presença por GPS/geofence | 13B/15 | **Implementada** com `lat/lng` obrigatórios no cadastro e fallback `UNVERIFIED` → estabelecimento; capitão não confirma |
| Trust Factor interno | 17 | **Implementado** na ADR 0041: −30 no-show, −7 cancelamento pós-confirmação, −2 pré-pagamento, recuperação não linear e restrição ranqueada |
| UI de presença/check-in no mobile | 13B/19 | Backend pronto; tela e revisão LGPD pendentes |
| Reversão/ajuste da ADR 0038 no código | 15 | **Concluída**: coluna, migração, lógica e testes da ADR 0038 foram removidos |
| Repasse à quadra em desistência pós-confirmação | 14B/15 | Valor não reembolsado permanece no ledger sem regra específica de repasse; decisão pendente |
| Check-in por localização e retenção LGPD | 19 | Definido na ADR 0039; implementação e revisão jurídica pendentes |
| Termos de uso e tela de pagamento com exemplos de cancelamento/substituição/ausência | 19 | Pendente de revisão jurídica |
| Reembolso real, MED e chargeback | 14B/15 | Apenas simulado |
| Conciliação periódica com PSP | 15 | Conciliação interna de referência; comparação com PSP real pendente |
| Repasse ao fornecedor | 15 | **Implementado como elegibilidade** em `starts_at + 2h` (ADR 0040); transferência real/PSP pendente |
| Janela de contestação antes/depois do repasse | 15 | Contestação `OPEN` suspende o repasse na proposta técnica; prazos **não definidos** |
| Extrato/recibos/comprovantes reais | 15 | Extrato interno existe; NFS-e e comprovantes fiscais pendentes |
| Interface financeira completa do fornecedor | 15 | Resumo, extrato, recebíveis e contestação como proposta técnica; exportação e comprovantes pendentes |
| Jornada mobile completa de reserva/quadra | 13B/13C | Vitrine, criação e pagamento existem no app; faltam cancelamento, presença, substituição e correção do pagador | Completar fluxo e testes |
| Revisão independente de fotos | 17 | Revisão inicial é feita pela organização |
| CEP do estabelecimento | 13F | **Fases 1 e 2 implementadas**: endpoint autenticado, BrasilAPI, cache, rate limit, `postal_code`/proveniência no venue e rebaixamento para `manual`. Mapa e pino ajustável pendentes | Implementar mapa/pino no painel |
| Provedor de geocoding de produção | 13F | BrasilAPI atende a Fase 1; Nominatim/Google e orçamento ainda não decididos |
| Precisão da coordenada da BrasilAPI | 13F | Coordenadas de bairro são rotuladas como `street`; CEPs vizinhos podem receber o mesmo ponto | Avaliar `approximate` ou provedor por endereço |
| Fallback de CEP/geocoding | 13F | BrasilAPI agrega Correios/ViaCEP/WideNet e devolve 404/504 quando todos falham; não há segundo provedor | Decidir ViaCEP (endereço) e Nominatim (coordenada) |
| Catálogo de avatares | 17 | Decisão registrada; implementação pendente |
| Kit da partida | 5/6/13 | Decisão registrada: **não bloqueia o lobby**; itens fixos são do estabelecimento. Implementação pendente |
| Catálogo definitivo de equipamento | 13/17 | Pendente; catálogo inicial (bola/rede) definido na ADR 0030 |
| Redirecionamento de quadra em recusa/expiração | 14B | Pendente |
| Limite de substituições | 14B | Pendente |
| `p_t` dinâmico por Trust Factor | 15/17 | Hipótese registrada na ADR 0036; não aprovada |
| Score de risco de pagamento | 15/17 | Só após dados reais de MED/chargeback |
| Integração da conclusão com o ciclo da partida | 15 | Hoje é ação operacional do estabelecimento |
| Testes de UI mobile | 19 | Ainda manuais |
| LGPD e retenção definitiva | 19 | Revisão jurídica pendente |
| Ledger de dupla entrada integrado | 14E | **Sombra de escrita feita na Etapa 6**; leitura alternável por `JOGA_TICKET_BALANCE_SOURCE` (Etapa 7). Falta 6b (passe/grátis/admin). |
| Taxa/preço em duas linhas | 14E | `compute_fee_cents` calcula e a reserva persiste `venue_price_cents`/`fee_cents`/`fee_percent_applied`/`total_cents` desde `m7d8e9f0a1b2`; o rateio usa `total_cents` e o repasse usa `venue_price_cents`. |
| CPF e NFS-e | 14E/19A | Placeholders; sem fluxo operacional |

## Crédito JOGA, 14E e NFS-e (ADR 0042/0049)

O modelo de crédito foi implementado como protótipo pelas fatias 14D.1–16, mas a ADR 0049 substitui a unidade de conta, o preço e a custódia. A **Fase 14E** é obrigatória antes de 14B/15 e de qualquer dinheiro real. O PSP do protótipo é o **Mercado Pago**; Inter PJ e Pagar.me ficam para o futuro.

| Pendência | Bloqueia | Próximo passo |
|---|---|---|
| Parecer fiscal: base de cálculo da comissão, ISS por município, retenção pelo tomador, IBS/CBS na transição | Produção com dinheiro real | Contador e advogado tributário |
| Parecer jurídico: intermediação, escrow, insolvência, 7 dias do CDC | Contrato e termos de uso | Advogado |
| Ledger de dupla entrada integrado | 14E | **Feito na Etapa 6** para os fluxos cobertos; falta a leitura (Etapa 7) e as vagas por passe/grátis/admin (Etapa 6b) |
| Preço em duas linhas e taxa persistida | 14E | `venue_price_cents`, `fee_cents`, `fee_percent_applied`, `total_cents` |
| Migração de lotes para saldo em reais | 14E | **Feita na Etapa 6**: `remaining_cents = remaining × 310` para compra/devolução, com `opening:{user}` contra `opening_equity`; passe/grátis/admin continuam em tickets |
| CPF e NFS-e | 14E/19A | Placeholders; definir fluxo e município |
| Custódia B→C e escrow | 19A | Contratar fornecedor de C |
| Reembolso parcial e política de passe/pacote | 14E/14B | Schema e regra pendentes |
| Programa de ingressos grátis (1 a cada 5 níveis no free, 2 no passe) | Definido | Medir custo real e conversão no piloto |
| Busca por CEP restrita ao passe | Definido | Definir exceção para mudança de cidade |
| Reajuste de preço e pausa do fornecedor | ADR 0042 §9 | Implementação no painel pendente |
| Nível da temporada e streak | Passe | **Definido na ADR 0043**: bronze/prata/ouro por nível, reseta; streak persiste |
| Venda do passe no meio da temporada e pro-rata | 14D.12 | **Implementado como três meses a partir do pagamento**; decidir restrição de janela |
| Conciliação de `purchase_payments` com o extrato do PSP | 14D.13/14B | Rotina interna implementada; falta comparação com PSP real |
| Lotes e validade | 14D.16/14E | Passe mensal e grátis de temporada; comprado sem validade. `ticket_lots.period` existe e o backfill de passe está em `m7d8e9f0a1b2`. |
| Recibo e comprovante do passe | 14D.12/19A | Depende de revisão fiscal |

## Estatísticas e inteligência de rede (ADR 0045)

A ADR 0045 esclarece a ADR 0043 §7 e §10 e detalha as estatísticas do passe e o painel de rede. O MMR bruto continua oculto (ADR 0025): "MMR" nas estatísticas é a leitura visível — divisão, progresso e posição. **Estatística essencial, histórico por quadra, passaporte e painel de rede implementados (14D.15).** Falta a camada visual e a calibração.

| Pendência | Bloqueia | Próximo passo |
|---|---|---|
| Evolução da divisão/progresso no mobile | 14D | Série existe em `rating_events`; falta o gráfico |
| Estatísticas do passe | 14D | **Histórico por quadra e passaporte implementados**; faltam evolução e retrospectiva |
| Inteligência de rede | 14D | **Implementada em faixas (14D.15)**; faltam densidade competitiva e tendência |
| Amostra mínima de 20 partidas em 30 dias | 14D | **Implementada**; calibrar no piloto |
| Horários com mais vaga por quadra | 14D | Depende da agenda de reservas |
| Estatísticas após o fim do passe | 14D | Definir o que permanece visível e o que é bloqueado |
| Painel B2B de ocupação | 15/14D | Definir acesso, preço e escopo |

## Clãs no MVP (ADR 0044)

Clãs e troféus deixam de ser fase posterior e passam a integrar o MVP, como pré-requisito do primeiro evento de marketing. **Backend implementado em 2026-11-13 (ADR 0046).**

| Pendência | Bloqueia | Próximo passo |
|---|---|---|
| Corte mínimo de moderação de chat de clã | Lançamento da Fase 16 | **Implementado**: denúncia, ocultação imediata, revisão de admin e registro; falta consequência para denúncia falsa (Fase 17) |
| Tamanho de clã, limites de entrada e regra de troca | Modelo de dados | **Definido**: 30 membros, aprovação, carência de 7 dias |
| Temporada de troféus e sua relação com a temporada trimestral | Troféus | **Definido**: mesma temporada trimestral, por formato, com snapshot |
| Fórmula de troféus | Troféus | **Definida como 50/30/20** (vitória/empate/derrota), 10 melhores membros e 7 dias de permanência; calibrar no piloto |
| Data-alvo do primeiro evento de marketing | Critério de saída da Fase 16 | Produto |
| Catálogo cosmético por temporada (livre, XP, passe) e balanceamento de XP | Customização | Modelo técnico em `docs/ESPECIFICACAO_TEMPORADA_E_CATALOGO.md`; falta arte e calibração |
| UI mobile de clã, chat e troféus | Fase 16 | Implementar telas e testes de UI |

## Moderação (Fase 17A)

| Pendência | Bloqueia | Próximo passo |
|---|---|---|
| Denúncia de perfil no lobby | 17A | **Implementada**: categorias, até 5 mensagens do alvo, limite diário e triagem determinística |
| Revisão humana | 17A/17C | **Implementada por CLI e painel web separado**; operadores em `moderation_operators` e bootstrap por `JOGA_MODERATION_ADMIN_USER_IDS` |
| Medidas reversíveis | 17A/17B | **Implementado**: aviso, restrição ranqueada e suspensão temporária de 1–30 dias; suspensão permanente fora da fatia |
| Recurso | 17A | **Implementado**: alvo recorre e outro operador decide; recurso aceito revoga a medida |
| IA de moderação | 17C | **Não usar IA paga**; avaliar modelo local/open-source após dataset rotulado |
| Denúncia falsa e limite por jogador | 17B | **Implementado**: 3 improcedentes em 30 dias geram cooldown de 7 dias |
| Suspensão temporária | 17B | **Implementada**: bloqueia autenticação e reativa por script ao fim do prazo |
| Suspensão permanente | 17C | Pendente de política, dupla revisão e revisão jurídica |
| Retenção/LGPD de contexto e evidências | 17B/19 | **Redação provisória em 180 dias**; revisão jurídica final pendente |
| Painel interno de moderação | 17C | **Implementado** em `/moderation`, separado do JOGA y GESTÃO; central interna pronta no backend (`/moderation/notifications`) | Consumir a central interna no painel |

## Reescopo das Fases 11–15 (ADR 0042/0043)

As fases 11–15 foram desenhadas para **reserva paga por participante**. A ADR 0042 mudou a cobrança, o reembolso e o recebedor; a ADR 0049 mudou a unidade de conta, o preço e a custódia. A 14D é protótipo do crédito; a **14E** é o reescopo obrigatório.

| Fase | Divergência | O que fazer | Estado |
|---|---|---|---|
| **12A** | A faixa/teto era tratada como preço | Preço do espaço + taxa em reais; faixa/tabela apenas como exibição/conversão | **Parcial (14D.1)**: faixa implementada; reclassificação para exibição na 14E |
| **12B** | Escopo era KYC de recebedor de marketplace | Cadastro de fornecedor: CNPJ, chave Pix de titularidade e contrato | **Técnico implementado (14D.2)**: CNPJ, chave tipada e `payout_ready`; falta KYC contratual/escrow |
| **13** | T3 = bloqueio **e pagamento** | T3 é janela de confirmação; no crédito não há cobrança na reserva | **Implementado (14D.5)**: T3 é janela de confirmação e a quitação é por crédito |
| **14A** | Uma cobrança Pix **por participante** | Compra de crédito/passe; `purchase_payments` | **Implementado (14D.13)** como protótipo; migrar para ledger em reais na 14E |
| **14C** | Reembolso **integral em dinheiro** | Devolução em crédito; dinheiro só nos 7 dias do CDC | **Parcial (14D.6)**: devolução em crédito; reembolso de passe/pacote pendente |
| **14E** | Unidade e preço ainda em tickets/2D; leitura do saldo ainda em `ticket_balances` | Saldo em reais, duas linhas, ledger de dupla entrada, CPF/NFS-e | **Em andamento**: Etapas 0–6 entregues; falta leitura (7), conformidade (8) e aposentadoria (9) |
| **15** | Extrato de **liberação de recebedor** | Extrato de **repasse ao fornecedor** sobre ledger em reais | Proposta local (15A/15B); refazer após 14E/14B |
| **10** | Threat model cita PSP/reservas antigos | Atualizar para MP, custódia B/C, crédito e NFS-e | **Atualizado em 16/11** |

**Fases 0–10 não mudam.** Identidade, perfil, matchmaking, partidas, resultados, MMR e tempo real são indiferentes ao meio de pagamento.

**Fase nova:** `14E — Realinhamento da ADR 0049` foi criada no `PLANS.md`; `14D` permanece como protótipo do crédito, e `14B` passa a ter escopo formal de hardening do Mercado Pago.

**Risco de execução:** a 13 e a 14A estão implementadas com testes. Mexer no T3, no crédito e no modelo de cobrança derruba cobertura existente. Tratar como reescopo de fase, com arquivo próprio em `harness/build/`, não como patch.

## Decisões financeiras não aprovadas (Fase 15)

A implementação 15A/15B é uma **proposta técnica local**. Estes pontos não são regra
aprovada e não devem ser tratados como decisão tomada:

| Item | Situação | Observação |
|---|---|---|
| `N = 24 h` | **Substituído** | ADR 0040 define repasse em `starts_at + 2h` |
| Liberação/repasse simulados no ledger | Não aprovado | Modelo financeiro final em aberto |
| Contestação por CLI | Não aprovado | CLI é provisória para testes; moderação financeira não definida |
| Divergência marcada como `FAILED` | Não aprovado | Salvaguarda técnica sem procedimento oficial |
| PSP real e conciliação externa | Parcialmente definido | Provedor e integração pendentes |

### Relógios distintos

| Relógio | Mede | Estado |
|---|---|---|
| Pagamento (T3) | Janela para pagar dentro do bloqueio da quadra | Requisito definido (estimativa inicial de 60 min) |
| Cancelamento (T5/cutoff) | Até quando é possível cancelar com reembolso/substituição | **Implementado** — configurável, padrão 6 h antes (`JOGA_CANCELLATION_CUTOFF_HOURS`) |
| Substituição (T4) | Quanto tempo o matchmaking tem para achar substituto | **Implementado** — 25% do tempo restante, piso 30 min, teto 12 h |
| Presença (T7/T8) | Pré-check-in e confirmação no local | **Implementada** na ADR 0039 (GPS/estabelecimento); UI mobile pendente |
| Contestação | Janela para o estabelecimento contestar valores/repasse | **Não definido** |
| Repasse/liberação | Quando o valor fica disponível e quando é transferido | **Definido na ADR 0040** (`starts_at + 2h`) e implementado como elegibilidade no ledger; transferência real pendente |

A implementação usa `eligible_at = starts_at + release_delay_hours` (padrão 2 h, ADR 0040) e permite contestação enquanto a liberação está `PENDING`. O relógio de contestação ainda não tem prazo definido.

## Dívidas técnicas conhecidas

- `MercadoPagoAdapter` usa credenciais do ambiente; testes continuam em simulador. Validação com credenciais reais pendente (MP-03).
- O webhook real depende de URL pública/túnel e segredo configurado no painel.
- O Mercado Pago (Orders API) é o PSP do protótipo com jogadores reais; Inter/Pagar.me ficam para o futuro (ADR 0048).
- O e-mail do pagador é obrigatório na Orders API; MP-04 adiciona e-mail ao usuário e remove o e-mail global fixo.
- O repasse ao fornecedor é um lançamento simulado no ledger; não há transferência real.
- O worker de reservas reembolsa com o adaptador configurado; se o PSP real falhar, a operação precisa de retry e conciliação.
- A interface financeira ainda não tem comprovantes, NFS-e, exportação nem contestação de MED/chargeback.
- `JOGA_RELEASE_DELAY_HOURS=2` é a regra da ADR 0040 (repasse em `starts_at + 2h`); a janela de contestação após o repasse continua pendente.
- A decisão de contestação financeira por CLI com `JOGA_REVIEW_OPERATORS` é **provisória para teste**; não é o modelo aprovado de moderação financeira.
- Marcar divergência de ledger como `FAILED` é uma salvaguarda técnica; o procedimento oficial de divergência não está definido.
- A implementação da ADR 0038 foi revertida. As fatias 1–6 da ADR 0039 têm fila, chamada automática, T4/T5, cancelamento individual, expiração, exclusão de reembolso, atribuição/pagamento, vaga paga em no-show, presença T6–T9, coordenadas obrigatórias e recomendação de formação. O Trust Factor interno está na ADR 0041; falta a UI de presença/suporte.
- O valor não reembolsado de desistência pós-confirmação ainda não tem regra de repasse/liberação à quadra; não liberar automaticamente sem decisão. A ADR 0039 determina que ele não pode virar receita silenciosa do JOGA.
- `cancellation_policy` voltou a `full_refund_until_confirmed`/`policy_version="v1"` após a reversão; a ADR 0039 exige novo rótulo/estrutura quando o fluxo completo existir. A oferta e os termos ainda precisam refletir a política consolidada.
- T6–T9 (presença/check-in), a atribuição/pagamento do substituto e a recomendação de formação estão implementados no backend; falta a UI mobile.
- O repasse ao fornecedor está definido na ADR 0040 (`starts_at + 2h`); a conciliação/repasse real com PSP continua pendente.

## Achados da auditoria de 16/11/2026

Itens descobertos na auditoria integral e ainda não implementados. São bloqueantes para 14E/14B/15 e para o piloto.

| Item | Severidade | Evidência | Ação |
|---|---|---|---|
| Ledger de dupla entrada não integrado | P0 | `LedgerService` só era usado em testes | **Corrigido na Etapa 6**: fluxos cobertos lançam na mesma transação; restam leitura (7) e 6b |
| Taxa calculada e não aplicada | P0 | `compute_fee_cents` sem chamador; reserva divide `price_cents` | 14E |
| T3 expirado não devolve ingressos | P0 | `bookings/service.py` | **Corrigido (onda 1)**: `expire_due` devolve ingressos; teste `test_t3_expiry_returns_tickets` |
| Pix pago + quitação por ingressos | P0 | `bookings/service.py` | **Corrigido (onda 1)**: vaga paga por Pix não consome ingresso; teste `test_pix_paid_seat_cannot_be_settled_with_tickets` |
| Reembolso não reverte repasse | P0 | `payments/service.py`; `REVERSED` sem uso | **Corrigido (onda 1)**: `refund_booking` marca release como `REVERSED`; teste `test_refund_reverses_venue_release` |
| Reembolso parcial impossível | P1 | unique por pagamento e valor integral | 14E/14B |
| Reembolso de compra não revoga crédito | P1 | `purchase.apply_status` ignorava `REFUNDED` | **Corrigido (onda 1)**: revoga crédito/assinatura; testes de pacote e passe |
| Estorno em `processing` marcado como falha/refunded | P0 | `payments/service.py` | **Corrigido (onda 1)**: fica `PENDING`, sem marcar jogador como `REFUNDED`; teste `test_refund_processing_does_not_mark_refunded` |
| Compra de pacote sem idempotência de requisição | P1 | `api/v1/tickets.py` | **Corrigido (onda 1)**: pendência única por jogador/pacote e teste de concorrência PostgreSQL |
| `EXPIRED` viola constraint de participante | P1 | `bookings/service.py` vs. model | **Corrigido (onda 1)**: constraint inclui `EXPIRED`/`CANCELLED`; teste de modelo |
| Webhook sem hash/rollback parcial | P0 | `payments/service.py`, `api/v1/payments.py` | **Corrigido (onda 1)**: hash do payload, conflito 409 e rollback antes de marcar falha; testes próprios |
| Migração `a6b7` e `env.py` com risco | P0 | nomes de constraint divergentes; imports ausentes | S0 |
| CI vermelha e teste com data fixa | P0 | 524/2/29; `ruff format` falha; `test_trust` | S0 |
| Payer da reserva errado no app | P1 | `venues.tsx:2075-2078` | Correção mobile |
| Retry de checkout no-op | P1 | `wallet.tsx:638,699-704` | Correção mobile |
| Documentação normativa desatualizada | P0 | técnica/DATA_MODEL/README/GOALS/RUNBOOK | Revisão 16/11 |

## Regra de avanço

- Não iniciar 14B, 15 ou 19 antes da 14E e dos pareceres da ADR 0049.
- Não iniciar 18 antes da 15 e da 19A.
- A 14E pode avançar sobre o ledger simulado, sem prometer dinheiro real.
- Fases 16–18 exigem autorização específica e registro em `PLANS.md`.
- Qualquer mudança de dinheiro real, custódia, KYC, NFS-e ou retenção exige ADR e revisão jurídica.
- O próximo passo autorizado é a estabilização do repositório, seguida da 14E.
