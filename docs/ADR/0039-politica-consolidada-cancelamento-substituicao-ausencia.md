# ADR 0039 — Política consolidada de cancelamento, substituição, presença e ausência

- **Status:** Política aprovada em 2026-11-09. Fatias 1–6 implementadas: reversão da ADR 0038, fila de substitutos, cancelamento individual, T4/T5, expiração, exclusão de reembolso, atribuição com pagamento/reembolso, vaga paga em no-show, presença T6–T9 (GPS/estabelecimento, sem capitão), coordenadas obrigatórias do estabelecimento, chamada automática da fila e recomendação automática de formação. O repasse no horário da partida está na ADR 0040; Trust Factor com pesos e UI de presença continuam pendentes.
- **Data:** 2026-11-09
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** ADR 0037 (reembolsos e conciliação no beta), ADR 0038 (desistência após confirmação, **superada por esta ADR**), ADR 0034 (Mercado Pago no beta), ADR 0021 (Pagar.me em produção); `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` §14; `docs/JOGA_DOCUMENTACAO_TECNICA.md` §14.6/§14.7 e §15.
- **Substitui:** ADR 0038, na parte que tratava qualquer desistência após `CONFIRMED` como definitivamente sem reembolso.

## Contexto

A política anterior confundia três situações diferentes:

1. O jogador **não comparece** (no-show), sem cancelar.
2. O jogador **cancela** depois da confirmação e há **substituto**.
3. O jogador **cancela** depois da confirmação e **não há substituto**.

Também não existia processo previsível para substituir alguém em cima da hora. A quadra não pode revender o horário enquanto o lobby existir, então a falta de substituto podia deixar o horário bloqueado e o valor sem destino claro.

## Decisão

### 1. O que o JOGA comercializa

O serviço contratado é a **participação em uma reserva coletiva de quadra**, vinculada a local, data, horário e duração. Matchmaking, formação de times e realização da partida são serviços de organização e melhor esforço, não garantia de comparecimento de todos. A comunicação e os termos devem explicar isso antes do pagamento.

### 2. Desfecho da reserva, não o status isolado

O destino financeiro é determinado pelo **desfecho da reserva coletiva**, não apenas por `CANCELLED_BY_PLAYER`. Estados possíveis:

- reserva cumprida e partida realizada;
- reserva cumprida, mas partida adaptada por ausência;
- reserva cancelada por falta de substituto/quórum;
- reserva cancelada por falha da quadra ou do JOGA;
- reserva não confirmada por pagamento/expiração.

### 3. Cancelamento antes da confirmação

Segue a ADR 0037: reembolso integral, incluindo taxa JOGA, quando a reserva não se completa por falta de pagamento, indisponibilidade, falha de substituição ou expiração.

### 4. Cancelamento depois da confirmação, antes do cutoff

- O jogador que cancela **não recebe reembolso**.
- O sistema abre a **janela T4 de substituição**.
- Se um substituto pagar a vaga, o substituído recebe reembolso da própria cobrança e a reserva continua; T3 não reinicia.
- Se T4 terminar sem substituto, o lobby é cancelado, o hold é liberado e os **demais participantes pagantes recebem reembolso integral**. Quem cancelou continua sem reembolso.
- O valor não reembolsado do cancelador não vira receita silenciosa do JOGA. O destino (compensação parcial da quadra ou crédito de boa-fé) é **pendência** e precisa de evento próprio no ledger.

### 5. Cancelamento depois do cutoff / no-show

- Depois do cutoff, não existe mais cancelamento voluntário com reembolso.
- Quem não confirma presença ou não comparece é **no-show**: sem reembolso.
- Um substituto da fila pode ocupar a vaga e **joga na vaga já paga**, sem nova cobrança.
- A quadra é considerada cumpridora se o horário foi mantido disponível; o repasse ocorre no horário da partida (ADR 0040) e não é afetado pela ausência.
- Se o grupo jogar com menos, aplica-se a regra de adaptação de formato.

### 6. Fila de substitutos

- Cada lobby pode ter uma fila de substitutos em standby.
- `F` = titulares do formato; `M` = mínimo para ainda haver jogo; `S = (F - M) + 1`, limitado a 4.
- Exemplos: 5x5 casual (10 titulares, mínimo 8) → alvo de 3; 6x6 casual → alvo de 5, limitado a 4; 3x3 → 1.
- Na prática, a fila pode ser menor. O caso comum é **+1 para fechar o time par**; o alvo acima é um teto operacional, não obrigação.
- Casual: fila opcional. Ranqueado: pelo menos 1 substituto em standby; se possível, 2.
- Substituto não é convocado até haver vaga. Ele confirma disponibilidade em T-2h; se não confirmar, sai da fila.
- **Chamada automática:** o sistema chama **no máximo um substituto por vez**, e **somente quando o número de ativos está ímpar**. Se o número está par, ninguém é chamado; se uma chamada pendente fica desnecessária porque o número virou par, ela é devolvida à fila.
- O chamado fica `CALLED` com prazo de resposta (`JOGA_SUBSTITUTION_CALL_TIMEOUT_MINUTES`, padrão 5 min). Aceita ou recusa; se recusar/expirar, o próximo é chamado se o número continuar ímpar.
- O objetivo é fechar um número par, não preencher todas as vagas.
- A atribuição manual pelo criador/organização continua disponível como fallback.
- Substituo chamado deve confirmar presença/chegada em T-15m; se não, chama o próximo.
- Ordem: disponibilidade confirmada, menor número de chamadas recentes e, no ranqueado, compatibilidade de nível/MMR.
- A fila não precisa estar cheia para o lobby casual existir. No ranqueado, fila insuficiente pode rebaixar o lobby para casual ou cancelá-lo com reembolso.

### 7. Presença e evidência

- **T-1h — pré-check-in:** titular confirma “vou comparecer”. No ranqueado é obrigatório; no casual é recomendado.
- **T-30m — presença no local:** confirmação por GPS/geofence ou pelo estabelecimento. Exemplo: partida às 19:00, todos no local até 18:30. **Não existe confirmação por capitão.**
- **T-15m — fechamento:** substitutos chamados precisam estar presentes/confirmados.
- A localização é validada no servidor (distância até a quadra, precisão, janela, partida, participante e idempotência). O cliente nunca decide sozinho `PRESENT`/`NO_SHOW`.
- O estabelecimento deve informar `latitude`/`longitude` no cadastro; sem coordenadas, o GPS fica `UNVERIFIED` e somente o estabelecimento pode confirmar.
- Privacidade: coletar localização apenas no check-in, não rastrear continuamente; armazenar resultado (dentro/fora do geofence), precisão, método e timestamp, não coordenadas cruas permanentes.
- Não confirmar presença em T-30m dispara a chamada automática de substitutos para as vagas de no-show.

### 8. Adaptação de formato

- O número de presentes pode formar um time válido com menos jogadores:
  - 5x5: 10 = 5x5; 9 = 4x4 + 1 rodízio; 8 = 4x4; 7 = 3x3 + 1; 6 = 3x3; 4 = 2x2; 2 = 1x1.
  - 6x6: 12 = 6x6; 11 = 5x5 + 1; 10 = 5x5; 9 = 4x4 + 1; 8 = 4x4; 7 = 3x3 + 1; 6 = 3x3; 4 = 2x2; 2 = 1x1.
  - 3x3: 9 = três times de 3; 8 = 4x4 ou 3x3 + 2; 7 = 3x3 + 1; 6 = 3x3; 4 = 2x2; 2 = 1x1.
- **Não existe quórum mínimo fixo.** Se houver pelo menos 2 jogadores, formam-se dois times com o número possível. Se houver 1, não há dois times.
- Em caso de número ímpar, o excedente entra em **rodízio** ou o sistema chama +1 da fila; não há reembolso.
- **Formação automática:** se o número de presentes é par, divide-se em dois times; se é ímpar, o sistema chama +1 da fila até alguém confirmar. A recomendação fica em `players_per_team`/`formation_note`.
- O rodízio não é cronometrado nem controlado pelo JOGA: o app apenas recomenda (ex.: “4x4 + 1 rodízio”). A partida continua sendo a mesma modalidade, com histórico de quem compareceu e quem faltou.
- Partida adaptada de 5x5 para 4x4 **não conta como 5x5 ranqueado**. Usar casual ou o MMR do formato efetivamente jogado.
- Reembolsar um jogador para “fechar 4x4” não fecha a conta: com 10 pagamentos e 1 falta, um reembolso deixa o valor abaixo do preço da quadra. Só é possível se a quadra reduzir o preço ou o JOGA conceder crédito de boa-fé.

### 9. Limites e ranking

- Limite inicial proposto: **2 cancelamentos confirmados por 30 dias**; acima disso, evento de Trust Factor e restrição temporária a partidas ranqueadas.
- Cancelamento do jogador afeta o **Trust Factor/ranking do jogador**, não o ranking da quadra.
- Cancelamento/falha da quadra afeta o **índice de confiabilidade comercial da quadra**, separado do Trust Factor do jogador.
- Emergências e força maior precisam de canal de exceção e análise; uma ausência isolada não gera punição pesada.
- No-show e desistência geram eventos auditáveis, com possibilidade de contestação.

### 10. Crédito de boa-fé

- Pode existir como ato voluntário, não contratual, financiado pelo JOGA.
- Registrar em evento próprio (`GOODWILL_CREDIT`), sem alterar a cobrança original nem o repasse da quadra.
- Não prometer quórum mínimo nem transformar o crédito em obrigação.

## Temporizadores

| Relógio | Quando começa | Duração proposta | Observação |
|---|---|---|---|
| T1 — confirmação dos jogadores | Criação da reserva | 60 min | Já existente |
| T2 — resposta da quadra | Fim do T1 | 30 min comercial, **máximo 60 min** | Sem teto de 4 h |
| T3 — pagamento | Aceite + hold | 60 min configurável | Já existente |
| T4 — substituição | Cancelamento após confirmação | **25% do tempo restante**, piso 30 min, teto 12 h | Termina sempre no cutoff |
| T5 — cutoff de cancelamento | — | **6 h antes** (proposta) | Depois, vira no-show |
| T6 — confirmação da fila | T-2h | até T-1h | Substituto confirma disponibilidade |
| T7 — pré-check-in | T-1h | até T-15m | Intenção; obrigatório no ranqueado |
| T8 — presença no local | T-30m | até T-15m | Geofence/QR/capitão |
| T9 — fechamento de substituto | T-15m | até T-0 | Se não preencher, adapta ou cancela |
| T10 — contestação financeira | Liberação/repasse | **não definido** | Pendente |
| T11 — repasse à quadra | Conclusão | **não definido** (`N`) | Pendente |

### Exemplo

Partida 19:00, 5x5, 10 titulares, 3 substitutos.

- **13:00 (T-6h):** cutoff de cancelamento.
- **17:00 (T-2h):** fila confirma disponibilidade; 3 confirmam.
- **18:00 (T-1h):** titulares fazem pré-check-in.
- **18:30 (T-30m):** todos no local confirmam presença. Dois não confirmam → dois substitutos são chamados.
- **18:45 (T-15m):** substitutos confirmam chegada; se um não vier, chama o terceiro.
- **19:00:** com 10, joga 5x5; com 9, 4x4 + rodízio; com 8, 4x4; abaixo do mínimo, cancela conforme a regra.

Se um titular cancela às 12:00 (antes do cutoff), T4 abre por 25% do tempo restante e termina no cutoff. Se achar substituto, o cancelador recebe reembolso e o substituto paga. Se não achar, o lobby é cancelado, os demais recebem reembolso e o cancelador não recebe.

## Matriz financeira

| Desfecho | Cancelador/ausente | Demais pagantes | Quadra |
|---|---|---|---|
| Reserva não confirma | Reembolso integral (ADR 0037) | Reembolso integral | Não recebe |
| Cancela antes do cutoff, com substituto | Reembolso | Seguem pagos | Recebe normal |
| Cancela antes do cutoff, sem substituto | Sem reembolso | Reembolso integral | Hold liberado; não recebe |
| No-show depois do cutoff | Sem reembolso | Sem reembolso | Recebe normal (reserva entregue) |
| Partida adaptada com menos jogadores | Sem reembolso | Sem reembolso | Recebe normal |
| Falha da quadra/JOGA | — | Reembolso integral | Não recebe |

## Consequências

- A ADR 0038 fica **superada** e sua implementação de código foi revertida.
- Fatia 1 entregue: `lobby_substitutes`, `booking_substitutions`, `booking_refund_exclusions`, T4/T5, endpoint de cancelamento individual, expiração no worker e reembolso dos demais sem incluir o desistente.
- Fatia 2 entregue: atribuição de substituto, cobrança da vaga, confirmação do pagamento, reembolso do substituído e fila marcada como `PLAYED`/`CONFIRMED` conforme o caso. Se o substituto não pagar até T4, a atribuição expira e o fluxo de cancelamento/reembolso dos demais é aplicado.
- Fatia 3 entregue: no-show após o cutoff cria vaga em `paid_seat=True`; o substituto ocupa a vaga já paga (`payment_status=WAIVED`, `covered_by_payment_id`), sem nova cobrança e sem reembolso ao ausente. Sem substituto até o prazo curto, a vaga expira, mas a reserva continua `CONFIRMED` e a quadra recebe normalmente.
- Fatia 4 entregue: pré-check-in, presença com GPS/estabelecimento, status `PRESENT`/`UNVERIFIED`/`NO_SHOW`, fechamento automático em T-30m e criação de vaga paga para ausentes. GPS só marca `PRESENT` se o local tiver coordenadas e o jogador estiver dentro do raio/precisão; caso contrário fica `UNVERIFIED` até confirmação do estabelecimento. Não há confirmação por capitão.
- Fatia 5 entregue: coordenadas obrigatórias no cadastro do estabelecimento, chamada automática da fila (`CALLED`/accept/decline/timeout) e recomendação automática de formação (`players_per_team`/`formation_note`).
- Ainda faltam: Trust Factor com pesos explícitos, UI de presença/fila e vínculo completo entre lobby/partida/reserva/pagamento.
- A vaga paga pelo ausente usa `covered_by_payment_id`/`payment_status=WAIVED`, sem cobrança dupla.
- O repasse à quadra em reserva entregue foi definido na ADR 0040: liberação no horário da partida.
- Nenhuma cobrança adicional, fundo ou aumento de taxa é criado por esta ADR.

## Pendências

- Percentual definitivo do T4 (proposta: 25%) e cutoff definitivo (proposta: 6 h).
- Quórum mínimo por modalidade e regra de adaptação ranqueada.
- Destino do valor não reembolsado do cancelador.
- Modelo de dados da fila e da vaga paga.
- Evidência de presença, fallback, retenção LGPD e contestação.
- Limite mensal definitivo e efeito no Trust Factor.
- Integração `advance_matches` ↔ reserva ↔ pagamento ↔ hold.
- Prazo de contestação e repasse (`N`), PSP real e conciliação externa.
- Revisão jurídica dos termos e da tela de pagamento.

## Critérios para revisão

- Piloto com taxa de no-show, cancelamentos, substituições e tempo de reposição.
- Incidentes de localização falsa/indisponível.
- Impacto no NPS e na confiabilidade das quadras.
- Revisão jurídica antes de dinheiro real.
