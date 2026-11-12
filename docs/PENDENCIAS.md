# Pendências abertas do JOGA

**Atualizado em:** 12 de novembro de 2026

Este arquivo consolida o que ficou aberto após as Fases 11–15 (sendo a 15 uma proposta técnica local, não política aprovada). Não substitui `PLANS.md`, os ADRs nem os arquivos de fase; serve como painel de acompanhamento.

## Bloqueios externos

| Pendência | Fase | Impacto | Próximo passo |
|---|---|---|---|
| PSP de produção (Inter PJ) | 14B | Sem Pix real, estorno, repasse e conciliação | Contratar conta PJ, validar taxa de 0,90% e perfil transacional |
| KYC do recebedor | 12B | Reserva paga não pode abrir sem recebedor `ACTIVE` | Decidir PSP/KYC e onboarding |
| SMS real | 10/19 | Login real depende de OTP | Escolher provedor, custo, antiabuso e LGPD |
| Push real | 10/19 | Notificações de prazo e resultado | Configurar APNs/FCM e credenciais |
| Mapas | 10/19 | Camada visual de descoberta | Pode esperar; usar lista/distância no início |
| CNPJ/MEI e revisão jurídica | 14B/19 | Dinheiro real e contratos | Definir entidade, contador e parecer jurídico |
| Storage de fotos de produção | 12A/19 | Fotos privadas e retenção | Escolher storage, criptografia e backup |

## Pendências de produto e engenharia

| Pendência | Fase | Estado |
|---|---|---|
| T2 em horário comercial | 14B | Hoje usa tempo corrido; falta calendário, feriados e dias fechados |
| T2 máximo de 60 min | 13B/14B | **Implementado** em 2026-11-09 (ADR 0039) |
| T3 configurável por estabelecimento | 13B/14B | Hoje usa configuração global |
| Política consolidada de cancelamento, substituição e ausência | 14B/15 | **Definida na ADR 0039**, que supera a ADR 0038; fatia 1 implementada, demais fatias pendentes |
| Fila de substitutos e timers T4–T9 | 13B/15 | Fatias 1–6 implementadas (fila, chamada automática, T4/T5, cancelamento, expiração, atribuição/pagamento, paid seat e presença T6–T9) |
| Adaptação de formato (4x4 + rodízio) | 13B/15 | **Recomendação automática implementada** (`players_per_team`/`formation_note`); rodízio controlado não existe |
| Vaga paga em no-show | 15 | **Implementada**: substituto `WAIVED`/`covered_by_payment_id`, sem nova cobrança |
| Presença por GPS/geofence | 13B/15 | **Implementada** com `lat/lng` obrigatórios no cadastro e fallback `UNVERIFIED` → estabelecimento; capitão não confirma |
| Trust Factor interno | 17 | **Implementado** na ADR 0041: −30 no-show, −7 cancelamento pós-confirmação, −2 pré-pagamento, recuperação não linear e restrição ranqueada |
| UI de presença/check-in no mobile | 13B/19 | Backend pronto; tela e revisão LGPD pendentes |
| Reversão/ajuste da ADR 0038 no código | 15 | **Concluída**: coluna, migração, lógica e testes da ADR 0038 foram removidos |
| Repasse à quadra em desistência pós-confirmação | 14B/15 | Valor não reembolsado permanece no ledger sem regra específica de liberação; decisão pendente |
| Check-in por localização e retenção LGPD | 19 | Definido na ADR 0039; implementação e revisão jurídica pendentes |
| Termos de uso e tela de pagamento com exemplos de cancelamento/substituição/ausência | 19 | Pendente de revisão jurídica |
| Reembolso real, MED e chargeback | 14B/15 | Apenas simulado |
| Conciliação periódica com PSP | 15 | Conciliação interna de referência; comparação com PSP real pendente |
| Repasse após a partida | 15 | **Implementado** na ADR 0040 (`starts_at + 2h`); repasse real/PSP pendente |
| Janela de disputa antes da liberação | 15 | Contestação `OPEN` suspende a liberação na proposta técnica; prazos **não definidos** |
| Extrato/recibos/comprovantes reais | 15 | Extrato interno existe; recibos e comprovantes fiscais pendentes |
| Interface financeira completa do estabelecimento | 15 | Resumo, extrato, recebíveis e contestação como proposta técnica; exportação e comprovantes pendentes |
| Jornada mobile completa de reserva/quadra | 13B | Painel de acompanhamento existe; falta seletor de quadra e criação |
| Revisão independente de fotos | 17 | Revisão inicial é feita pela organização |
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

## Ingresso JOGA (ADR 0042)

Modelo aprovado como direção de produto, **não implementado**. Nenhuma fase comercial foi aberta.

| Pendência | Bloqueia | Próximo passo |
|---|---|---|
| Parecer fiscal: base de cálculo da comissão, ISS por município, retenção pelo tomador, IBS/CBS na transição | Produção com dinheiro real | Contador e advogado tributário |
| Parecer jurídico: intermediação, conta segregada, saldo em insolvência, 7 dias do CDC | Contrato e termos de uso | Advogado |
| `C_c` recalibrado para R$ 0,47 por reserva cancelada (`q` = 75%) | Feito | Validar `q` e `C_c` com dados reais do piloto; a tabela se move ±1 ingresso por faixa |
| Custódia, Payouts no Brasil e Pix Automático por API em cada PSP | PSP de produção | Comercial dos PSPs |
| Taxonomia final de atributos e teto de V por faixa | Contrato com a quadra | Produto e comercial |
| Programa de ingressos grátis (1 a cada 5 níveis no free, 2 no passe) | Definido | Medir custo real (3,3%/6,7% da receita) e conversão no piloto |
| Busca por CEP restrita ao passe | Definido | Definir como o usuário free que mudou de cidade ou planeja jogar fora resolve isso (ex.: troca de cidade base com limite) |
| Reclassificação de faixa com aviso de 30 dias | 14D.1 entregou teto e reajuste | Decorrido: a quadra reajusta e a faixa é recalculada; falta o aviso contratual de 30 dias |
| Arredondamento de 4x4 | Tabela 2D | Produto |
| Reajuste de preço e pausa do estabelecimento | Definido na ADR 0042 §9 | Implementação no painel pendente |
| Orçamento do crédito de estreia | Funil de aquisição | Produto e financeiro |
| Nível da temporada e streak | Passe | **Definido na ADR 0043**: bronze/prata/ouro por nível, reseta; streak de vitórias persiste |

## Clãs no MVP (ADR 0044)

Clãs e troféus deixam de ser fase posterior e passam a integrar o MVP, como pré-requisito do primeiro evento de marketing.

| Pendência | Bloqueia | Próximo passo |
|---|---|---|
| Corte mínimo de moderação de chat de clã | Lançamento da Fase 16 | Definir canal de denúncia e medidas mínimas |
| Tamanho de clã, limites de entrada e regra de troca | Modelo de dados | Produto |
| Temporada de troféus e sua relação com a temporada trimestral | Troféus | Produto |
| Data-alvo do primeiro evento de marketing | Critério de saída da Fase 16 | Produto |
| Catálogo cosmético por temporada (livre, XP, passe) e balanceamento de XP | Customização | Modelo técnico em `docs/ESPECIFICACAO_TEMPORADA_E_CATALOGO.md`; falta arte e calibração |

## Reescopo das Fases 11–15 (ADR 0042/0043)

As fases 11–15 foram desenhadas para **reserva paga por participante**. O ingresso mudou três objetos: a cobrança, o reembolso e o recebedor. Nada disso é ajuste de texto — é reescopo de schema e de máquina de estados.

| Fase | Divergência | O que fazer | Estado |
|---|---|---|---|
| **12A** | `venue_spaces` tem preço livre; a tabela 2D exige faixa com atributo e teto | Criar `pricing_bands` versionada, vincular cada quadra a uma faixa e implementar reajuste "sem reserva afetada" | **Implementado (14D.1)**: faixa resolvida por teto, `is_covered` e reajuste que vale só para reservas novas |
| **12B** | Escopo era KYC de recebedor de marketplace | Reescrever para cadastro de fornecedor: CNPJ, chave Pix de titularidade e contrato com teto | **Implementado (14D.2)**: CNPJ com dígito verificador, chave Pix tipada, chave mascarada e `payout_ready`. Falta KYC contratual e portão na reserva |
| **13** | T3 = bloqueio **e pagamento** | T3 passa a ser janela de confirmação; no fluxo de ingresso não há cobrança na reserva | Pendente |
| **14A** | Uma cobrança Pix **por participante** | Cobrança por compra de pacote ou passe; `purchase` + `ticket_ledger` | Pendente |
| **14C** | Reembolso **integral em dinheiro** | Devolução em ingresso; dinheiro só nos 7 dias do CDC | Pendente |
| **15** | Extrato de **liberação de recebedor** | Extrato de **repasse ao fornecedor**; "recebíveis" viram "repasse a receber" | Pendente (código não commitado) |
| **10** | Threat model cita adaptadores de PSP antigos | Atualizar para Inter e para o fluxo de ingresso | Pendente |

**Fases 0–10 não mudam.** Identidade, perfil, matchmaking, partidas, resultados, MMR e tempo real são indiferentes ao meio de pagamento.

**Fase nova:** `14D — Ingresso, carteira e temporada` foi criada no `PLANS.md`. O ingresso, a temporada e o catálogo não tinham fase; agora têm escopo, dependências e critérios de aceite.

**Risco de execução:** a 13 e a 14A estão implementadas com testes. Mexer no T3 e no modelo de cobrança derruba cobertura existente. Tratar como reescopo de fase, com arquivo próprio em `harness/build/`, não como patch.

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

- `MercadoPagoAdapter` usa sandbox e não deve operar dinheiro real.
- O webhook real depende de URL pública/túnel e segredo configurado no painel.
- O adaptador de produção (**Inter**) ainda não existe; o código só tem `simulator` e `mercadopago` em sandbox.
- O e-mail do pagador é obrigatório na Orders API do Mercado Pago; o cadastro atual é por telefone. Falta decidir de onde o e-mail vem.
- O repasse ao estabelecimento é um lançamento simulado no ledger; não há transferência real.
- O worker de reservas reembolsa com o adaptador configurado; se o PSP real falhar, a operação precisa de retry e conciliação.
- A interface financeira ainda não tem comprovantes, exportação nem contestação de MED/chargeback.
- `JOGA_RELEASE_DELAY_HOURS=2` é a regra da ADR 0040 (repasse em `starts_at + 2h`); a janela de contestação após liberação continua pendente.
- A decisão de contestação financeira por CLI com `JOGA_REVIEW_OPERATORS` é **provisória para teste**; não é o modelo aprovado de moderação financeira.
- Marcar divergência de ledger como `FAILED` é uma salvaguarda técnica; o procedimento oficial de divergência não está definido.
- A implementação da ADR 0038 foi revertida. As fatias 1–6 da ADR 0039 têm fila, chamada automática, T4/T5, cancelamento individual, expiração, exclusão de reembolso, atribuição/pagamento, vaga paga em no-show, presença T6–T9, coordenadas obrigatórias e recomendação de formação. O Trust Factor interno está na ADR 0041; falta a UI de presença/suporte.
- O valor não reembolsado de desistência pós-confirmação ainda não tem regra de repasse/liberação à quadra; não liberar automaticamente sem decisão. A ADR 0039 determina que ele não pode virar receita silenciosa do JOGA.
- `cancellation_policy` voltou a `full_refund_until_confirmed`/`policy_version="v1"` após a reversão; a ADR 0039 exige novo rótulo/estrutura quando o fluxo completo existir. A oferta e os termos ainda precisam refletir a política consolidada.
- T6–T9 (presença/check-in), a atribuição/pagamento do substituto e a recomendação de formação estão implementados no backend; falta a UI mobile.
- O repasse à quadra de reserva entregue está definido na ADR 0040 (no horário da partida); a conciliação/repasse real com PSP continua pendente.

## Regra de avanço

- Não iniciar 14B sem PSP/contrato e autorização.
- Fase 15 pode avançar sobre o ledger simulado, sem prometer repasse real.
- Fases 16–18 exigem autorização específica e registro em `PLANS.md`.
- Qualquer mudança de dinheiro real, custódia, KYC ou retenção exige ADR e revisão jurídica.
