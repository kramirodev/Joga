# ADR 0038 — Desistência após confirmação e ausência de jogadores

> **Esta ADR foi superada pela ADR 0039.** A regra consolidada distingue cancelamento com substituição, cancelamento sem substituto e no-show, e determina o destino financeiro pelo desfecho da reserva, não apenas pelo status `CONFIRMED`. Consulte `0039-politica-consolidada-cancelamento-substituicao-ausencia.md`.

- **Status:** **Superada pela ADR 0039 em 2026-11-09.** Mantida para histórico. O bloqueio de reembolso foi implementado, mas será revertido/ajustado para a lógica de desfecho da ADR 0039.
- **Data:** 2026-11-09
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** ADR 0037 (reembolsos e conciliação no beta), ADR 0034 (Mercado Pago no beta), ADR 0021 (Pagar.me em produção); `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` §14; `docs/JOGA_DOCUMENTACAO_TECNICA.md` §14.6 e §15.
- **Emenda:** substitui, para o caso de desistência após confirmação, o item 1 da ADR 0037, que reembolsava `CANCELLED_BY_PLAYER` em qualquer estado não terminal.

## Contexto

Depois que todos os participantes pagam, a quadra aceita a reserva e o bloqueio é confirmado,
o compromisso comercial já foi assumido com o estabelecimento. Pode haver desistência
individual, ausência no dia ou partida inviabilizada porque poucos jogadores compareceram.

Era preciso decidir se o JOGA reembolsaria quem compareceu, quem desistiu e quem faltou, e
quem absorveria o custo. A ADR 0037 havia mantido a política de cancelamento após confirmação
em aberto.

## Decisão

1. **O serviço contratado é a reserva coletiva da quadra**, em local, data, horário e
   duração definidos. Matchmaking, formação de times e realização da partida são melhor
   esforço, não garantia de que todos comparecerão.
2. **Antes da confirmação:** cancelamento, expiração, indisponibilidade ou falha de
   substituição seguem a ADR 0037 e reembolsam integralmente o que foi pago, incluindo a
   taxa JOGA.
3. **Depois da confirmação:** o jogador que desistir **não recebe reembolso**. O produto já
   foi comprado e a quadra já foi reservada. A desistência pode ser registrada e auditada,
   mas não gera devolução automática.
4. **Substituição é exceção:** se houver substituição efetiva por outro jogador que pague a
   vaga, o participante substituído recebe reembolso da própria cobrança, como já ocorre na
   Fase 14C. Isso não é tratado como cancelamento da reserva.
5. **Ausência/no-show:** o faltante não recebe reembolso. A contribuição dele permanece na
   reserva e não é redistribuída aos presentes.
6. **Partida inviabilizada por ausências:** os jogadores presentes **não** recebem reembolso
   automático, porque a quadra foi disponibilizada. O JOGA não cobre a vaga de quem faltou
   nem aumenta a taxa para formar fundo de compensação.
7. **Falha da quadra ou do JOGA:** se o estabelecimento não disponibilizar o espaço,
   cancelar, descumprir o bloqueio ou se o JOGA falhar na reserva, aplica-se reembolso
   integral, independentemente do estado, respeitados os direitos legais do consumidor.
8. **Crédito de boa-fé:** casos extremos podem receber crédito ou voucher discricionário,
   financiado pelo JOGA, sem natureza contratual e sem retirar valor da quadra. Se
   implementado, deve ser registrado em evento próprio do ledger, nunca como
   `PAYMENT_REFUNDED` da cobrança original.
9. **Transparência:** a regra deve ser apresentada antes do pagamento, nos termos de uso e
   nas condições da reserva, com exemplos claros. Não pode haver cláusula absoluta que
   elimine direitos legais do consumidor.
10. **Consequências de confiabilidade:** desistência após confirmação e ausência podem gerar
    eventos de Trust Factor em fase própria, sem punição automática por evento isolado e sem
    cobrança monetária adicional.

## Matriz de reembolso

| Evento | Reembolso ao jogador | Absorve o custo |
|---|---|---|
| Reserva não confirma (pagamento/expiração/substituição) | Integral | Fluxo da ADR 0037 |
| Desistência antes da confirmação | Integral | Fluxo da ADR 0037 |
| Desistência depois da confirmação, sem substituto | Nenhum | Próprio jogador |
| Desistência depois da confirmação, com substituto pagante | Integral ao substituído | Substituto |
| Ausência/no-show | Nenhum | Próprio jogador |
| Partida inviável apenas por ausências | Nenhum aos presentes | Ninguém; a reserva foi entregue |
| Quadra não disponibiliza/cancela | Integral | Quadra/JOGA, conforme contrato |
| Falha do JOGA na reserva | Integral | JOGA |

## Distinção dos três relógios

Esta ADR não define os prazos operacionais de pagamento, contestação ou repasse. Eles
continuam distintos:

- **Pagamento (T3):** janela para pagar dentro do bloqueio da quadra; requisito já definido.
- **Contestação:** janela para contestar valores/repasse; **pendente**.
- **Repasse/liberação:** quando o valor fica disponível e quando é transferido; **pendente**.

## Consequências

- A ADR 0037 permanece válida para estados anteriores à confirmação.
- O bloqueio de reembolso foi implementado em `bookings.cancellation_refund_allowed`,
  aplicado no cancelamento do jogador e respeitado pelo worker de reembolso. `BookingService`
  passa a gravar `cancellation_policy="no_refund_after_confirmation"` e `policy_version="v2"`.
- **Pendência:** o valor não reembolsado de uma desistência após confirmação permanece no
  ledger, mas ainda não há regra específica de repasse/liberação à quadra para esse caso.
  Não implementar liberação automática sem decisão explícita.
- O reembolso de substituto continua permitido e já está implementado.
- Nenhuma cobrança adicional, fundo ou aumento de taxa é criado por esta decisão.
- Termos de uso, tela de pagamento e política de cancelamento precisam de revisão jurídica
  antes de dinheiro real.

## Alternativas consideradas

### A. Reembolsar todos os presentes quando faltar alguém

Rejeitada. Transferiria ao JOGA e aos demais o custo de uma ausência individual, incentivaria
abuso e exigiria aumentar taxa ou provisão.

### B. Reembolsar quem desiste depois da confirmação

Rejeitada. A quadra já foi reservada e o compromisso financeiro assumido; o reembolso
deixaria o custo para os demais ou para o JOGA. A substituição continua sendo o caminho para
recuperar a vaga.

### C. Proibir a desistência depois da confirmação

Não é necessária. A desistência pode ser registrada e auditada; o efeito financeiro é que não
há reembolso. A vaga pode ser substituída se houver candidato.

### D. Crédito de boa-fé discricionário (adotada como possibilidade)

Reduz risco reputacional em casos extremos sem criar garantia contratual nem prometer quórum.
Fica limitado a decisão caso a caso e financiado pelo JOGA.

## Critérios para revisão

- Revisão jurídica dos termos, da oferta e da política de cancelamento (CDC).
- Definição dos três relógios e do modelo de repasse/PSP.
- Dados do piloto: taxa de no-show, partidas abaixo do quórum, contestações e NPS.
- Implementação de eventos de Trust Factor para ausências e desistências (Fase 17).
