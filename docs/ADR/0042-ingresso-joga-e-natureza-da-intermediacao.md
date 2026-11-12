# ADR 0042 — Ingresso JOGA, tabela 2D e natureza da intermediação

- **Status:** Aprovado como direção de produto; não implementado.
- **Data:** 2026-11-11
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** ADR 0021 (precificação e fluxo financeiro), ADR 0022 (sem marketplace de produtos), ADR 0025 (MMR/rankings/cosméticos), ADR 0034 (Mercado Pago no beta), ADR 0037 (reembolsos e conciliação), ADR 0039 (cancelamento, substituição e ausência), ADR 0040 (repasse no horário da partida). Substitui a ADR 0021 **no fluxo de ingresso**, preservando dela os componentes de custo e a regra de elegibilidade.

## Contexto

A ADR 0021 precifica cada reserva com a fórmula `TAXA = c·V + C_k + C_c·μ·S + p_t·V`, resolvida como ponto fixo sobre o valor da quadra. Esse desenho tem duas características que impedem o fluxo pretendido: o jogador vê reais e vê o valor da quadra, e o pagamento acontece por reserva, obrigando o organizador a cobrar cada participante.

O produto precisa de um fluxo silencioso: o jogador escolhe onde e quando jogar, usa uma unidade de acesso pré-paga e não vê preço de quadra nem equivalência em reais. A tentativa de simplesmente arredondar a fórmula para tickets produziu dois defeitos mensuráveis: saltos de preço de até 50% entre faixas vizinhas e comissão efetiva de 40% a 60%, o dobro do alvo, porque o arredondamento incide por jogador.

A saída foi separar o que a fórmula faz do que a tabela faz: a fórmula deixa de gerar o preço e passa a ser o piso e a calibração; o preço passa a vir de uma tabela discreta. Esta ADR registra essa separação, a natureza jurídica escolhida e o desenho do ingresso, do passe e da conta do ingresso.

## Decisão

### 1. Natureza jurídica: intermediação

1. O JOGA atua como **intermediador** entre jogador e estabelecimento no fluxo de ingresso. Não é revenda e não é instituição de pagamento.
2. O saldo de ingressos é obrigação do JOGA **com o jogador**; a parte da quadra é obrigação **com o estabelecimento**, reconhecida no momento da reserva.
3. A base de cálculo pretendida dos tributos sobre a receita é a **comissão** (preço do ingresso menos o valor da quadra), não o valor cheio. A confirmação é pendência fiscal bloqueante: sem parecer, não há produção com dinheiro real.
4. A intermediação exige **conta segregada**, identificação da parte da quadra na reserva e repasse em `starts_at + 2h` (ADR 0040).
5. A intermediação remove o JOGA da posição de dono do float: o rendimento do saldo carregado não é receita própria e não pode ser tratado como margem.

### 2. Ingresso JOGA

1. O ingresso é uma **unidade de acesso pessoal**, com preço de referência de **R$ 3,10** (pacote grande, base da tabela) e R$ 3,70 no avulso.
2. O jogador vê apenas ingressos. Reais aparecem somente no checkout de pacote e de passe.
3. O ingresso é **consumido na confirmação da reserva**, não no check-in. Preserva a matriz da ADR 0039.
4. Devolução é sempre em **ingressos**, para o mesmo saldo (ADR 0039 e ADR 0037).
5. Ingresso **comprado nunca expira**.
6. O ingresso é **intransferível**: sem presente, revenda, transferência entre contas ou saque. A única exceção é o direito de arrependimento de 7 dias (CDC art. 49), liquidado em dinheiro.
7. A intransferibilidade é **guardrail regulatório**, não apenas antifraude: é o que mantém o ingresso como crédito de serviço e não como conta de pagamento.

### 3. Tabela 2D: formato × faixa

1. O custo em ingressos depende de **formato** e de **faixa**. A faixa é ancorada em atributo visível ao jogador (cobertura, dia/noite), nunca no preço da quadra.
2. Tabela inicial (ingressos por jogador):

| Faixa | 5x5 (10) | 6x6 (12) | 4x4 (8) | 3x3 (6) |
|---|---:|---:|---:|---:|
| Econômica dia (até R$ 120) | 5 | 4 | 6 | 8 |
| Econômica noite (R$ 121–150) | 6 | 5 | 8 | 10 |
| Padrão dia (R$ 151–180) | 7 | 6 | 9 | 12 |
| Padrão noite (R$ 181–220) | 9 | 7 | 11 | 14 |
| Coberta (R$ 221–260) | 10 | 9 | 13 | 17 |
| Premium (R$ 261–300) | 12 | 10 | 14 | 19 |

3. **Faixas adjacentes diferem em 1 ingresso**, salvo quando a diferença coincide com mudança de atributo visível. Os saltos de 2 ocorrem nas fronteiras de atributo (Padrão dia e Coberta).
4. O degrau unitário é `T / (V/n)`. Com `T = R$ 3,10` e vaga de R$ 15,00, o degrau é 21%. Preço de ingresso maior produz degraus maiores; R$ 6,20 foi rejeitado.
5. A margem líquida resultante fica entre **10,2% e 22,6%** no topo de cada faixa, com `T = R$ 3,10` e a pilha de custos da seção 5.
6. 4x4 arredonda para cima e gera cerca de R$ 24 por partida acima do alvo de receita. Aceito no piloto, revisável.
7. O preço unitário é **decrescente por tamanho de compra**, para que o pacote grande seja viável sem encarecer o avulso:

| Oferta | Ingressos | Unitário | Total |
|---|---:|---:|---:|
| Avulso | 3 | R$ 3,70 | R$ 11,10 |
| Pequeno | 10 | R$ 3,40 | R$ 34,00 |
| Médio | 30 | R$ 3,20 | R$ 96,00 |
| Grande | 50 | R$ 3,10 | R$ 155,00 |
| Passe | franquia mensal | R$ 3,25 | — |

8. A tabela é calibrada no **menor preço praticado** (R$ 3,10, pacote grande). Todo preço acima disso é margem adicional. O passe é mais caro por ingresso que o pacote grande porque entrega franquia mensal, ingressos grátis por nível e Temporada — não é desconto, é assinatura.

### 4. Passe trimestral com franquia mensal

1. O passe é o produto principal. Tamanhos: **10, 20, 30 e 50 ingressos por mês**.
2. A franquia do passe é **mensal e não acumula**. Ingresso de passe não convertido em comprado.
3. Ingressos **comprados** não expiram e formam reserva permanente.
4. Ordem de consumo: **primeiro a franquia do passe, depois os comprados**.
5. Ingresso de passe devolvido por cancelamento volta para a franquia do mês; se o mês já virou, não vira ingresso comprado.
6. O benefício do passe é em **quantidade fixa**, nunca percentual sobre o preço unitário. Desconto percentual por ingresso se multiplica pelo número de ingressos da partida e derruba a margem das faixas caras abaixo do piso.
7. O passe inclui a Temporada premium (cosméticos e status). Nunca vantagem competitiva.
8. Renovação por Pix por ciclo no MVP. Pix Automático é opcional e posterior.

### 5. Conta do ingresso e piso de margem

1. Três buckets no ledger: **custeio da reserva**, **faturamento** e **margem JOGA**.
2. Pilha de custos por partida: **PSP de 0,99%** sobre a receita, **provisão de cancelamento de R$ 0,60 por jogador** (`C_c = R$ 0,47` por reserva cancelada, validado de baixo para cima: atendimento, reembolso CDC, reprocessamento da fila; não há tarifa de PSP a recuperar nem devolução em dinheiro), custo fixo de `R$ 4,00`, imposto de 6% sobre a comissão e **conformidade da custódia de 0,4% do saldo carregado**.
3. **Margem é saída, não entrada.** `margem_liquida = (R − custeio) / V`. A variável `c` da ADR 0021 deixa de existir como premissa.
4. Piso: **10% líquido**, avaliado **no topo da faixa** e **depois** do programa de ingressos grátis. Alvo: 12%.
5. Com intermediação, o piso de 10% se sustenta até quadra de aproximadamente **R$ 125** na faixa de 5 ingressos. A regra de 25% da ADR 0021 deixa de se aplicar ao fluxo de ingresso.
6. **O passe não tem desconto por ingresso.** Seu benefício é franquia mensal, ingressos grátis por nível e Temporada. Faixa abaixo do piso não recebe benefício adicional.
7. A provisão de 100% do passivo é **política interna de liquidez**, não segregação jurídica. Em insolvência, o portador do ingresso é credor quiroquistário.
8. **O float não é receita, não é margem e não é lucro.** Ele é posição de balanço: caixa de um lado, obrigação do outro. Seu único efeito econômico é dispensar capital de giro — um financiamento que não precisa ser contratado. Nunca lançar rendimento de float como receita, nem breakage de ingresso não usado como resultado.

### 6. Matchmaking

1. A busca começa pela **intenção**: região, janela de horário, formato, nível e distância.
2. O saldo é **restrição sobre o resultado**, nunca a consulta.
3. Entre as partidas elegíveis, o ranking usa distância, horário, nível e qualidade da quadra. Custo em ingressos não é critério de ordenação.
4. `MIN_TICKETS` é definido **por formato e faixa**, não global.
5. Limite de busca: 3 faixas ou 2 minutos na busca instantânea; 24h na assíncrona. Sem resultado, oferecer aumento de saldo, ampliação de região/horário ou fila de espera.
6. **A origem da busca é a localização do aparelho.** Busca por **CEP** é benefício do passe (ADR 0043 §4): declarar intenção em qualquer lugar enche o motor de partidas que não vão acontecer, e a barreira de custo reduz esse volume.

### 7. Crédito de estreia

1. Crédito patrocinado de **1 partida** em faixa elegível (Econômica ou Padrão dia), validade de 14 dias.
2. Definido em partidas, não em ingressos: evita saldo residual e não revela o preço unitário.
3. Intransferível, não conversível em dinheiro, custo de marketing.

### 8. PSP

1. **Teste:** Mercado Pago, como já registrado na ADR 0034.
2. **Produção: Inter PJ.** Conta corrente (não conta de pagamento), API Pix e de extratos gratuita, Pix de saída gratuito. Taxa: **0,90% no QR dinâmico imediato** (mínimo R$ 0,10, teto R$ 1,50). O teto faz o passe grande custar 0,35% por real. Usar QR imediato, não o com vencimento (0,99%).
3. **Reserva técnica: Pagar.me**, não por taxa, mas como segunda conta operacional contra congelamento.
4. O `PspAdapter` expõe três operações abstratas: `create_pix_charge`, `create_subscription` e `create_payout`.
5. **Não são requisitos:** Pix Automático por API, Payouts em lote, escrow, motor de assinatura e rendimento do float. O passe é compra única trimestral, não recorrência.

### 9. Reajuste de preço e pausa do estabelecimento

1. O gatilho para reajuste não é "não haver nenhuma reserva", é **não haver reserva afetada**. Exigir inventário vazio congelaria o preço de qualquer quadra movimentada e obrigaria o estabelecimento a cancelar reservas para reajustar.
2. Reajuste vale apenas para **janelas futuras sem reserva** e nunca é retroativo. A reserva confirmada mantém o preço e a versão da tabela vigentes no momento da reserva.
3. Reajuste entra na **virada de temporada**, com aviso mínimo de 30 dias.
4. Reajuste **dentro da faixa** é livre. Mudar de faixa exige reclassificação e só afeta reservas futuras.
5. "Pausada" e "fechada temporariamente" são **estados de disponibilidade**, independentes de preço. Bloqueiam novas reservas e não são ferramenta de reajuste.
6. **Pausar com reserva confirmada no período é falha do estabelecimento** (ADR 0039): devolução integral em ingressos aos jogadores, sem repasse, e evento contratual. Sem essa regra, pausar vira a rota de fuga para não honrar reserva barata.
7. O painel registra autor, data, valor anterior, valor novo e motivo de cada reajuste e de cada pausa. Auditoria mensal.

### 10. O que não muda

1. **Publicidade** continua subordinada à audiência, identificada como patrocinada e proibida de alterar MMR, Trust Factor, matchmaking ou troféus de clã (Fase 18).
2. **Customização** permanece sem vantagem competitiva. A regra original de "cosméticos não comprados" foi **emendada pela ADR 0043 §5**: configuração é perk do passe, conquista é sempre por XP, e identidade e acessibilidade nunca são pagas.
3. **Gamificação** continua sem vantagem comprada: Temporada, streak, badges e passaporte de quadras.
4. **Zero mercado de saldo**: sem transferência, revenda, saque ou P2P.

## Consequências

- A ADR 0021 permanece válida para reserva avulsa sem ingresso; no fluxo de ingresso ela é substituída por esta ADR.
- O preço de uma partida passa a ser um número inteiro de ingressos, e a margem por partida varia dentro de cada faixa.
- O estabelecimento passa a ter **teto de V por faixa** em contrato, com reclassificação automática, aviso de 30 dias e auditoria mensal. Sem teto, a faixa sofre *band creep* até a margem zerar.
- A receita deixa de ser por reserva e passa a ser por consumo de ingresso; a venda de pacote é passivo, não receita.
- O imposto tem duas visões obrigatórias: na venda (caixa) e no consumo (competência).
- Nenhuma fase comercial está implementada. Este documento não autoriza código.

## Pendências

1. Parecer fiscal: base de cálculo da comissão, ISS por município, retenção pelo tomador, IBS/CBS na transição.
2. Parecer jurídico: intermediação, conta segregada, tratamento do saldo em insolvência, fluxo dos 7 dias do CDC.
3. Recalibrar `C_c` para o fluxo de ingresso; R$ 15,87 é conservador e não definitivo.
4. Confirmar custódia, Payouts no Brasil e Pix Automático por API em cada PSP.
5. Definir taxonomia final de atributos (cobertura, dia/noite) e teto contratual por faixa.
6. Revisar o arredondamento de 4x4.
7. Definir orçamento do crédito de estreia.
8. Decidir se o passe terá nível (bronze/prata/ouro) e se a Temporada é mensal.
