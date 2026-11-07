# ADR 0033 — Reservas e temporizadores na Fase 13A

- **Status:** Aprovado para a 13A em 2026-11-07; 13B, PSP real e horário comercial pendentes.
- **Data:** 2026-11-07
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** `PLANS.md` Fase 13; `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` §10.3–10.8 e §11; `docs/JOGA_DOCUMENTACAO_TECNICA.md` §14.

## Contexto

A Fase 12A criou quadras, agenda e bloqueios, mas ainda não existe reserva. A Fase 13 precisa transformar um lobby em solicitação, obter aceite do estabelecimento, bloquear o espaço e controlar T1/T2/T3 sem dupla reserva nem confiar no cliente. A 13A implementa o backend sem movimentar dinheiro real.

## Decisão

1. A reserva nasce em `PARTICIPANT_CONFIRMATION` (T1), vinculada a um lobby, organização, estabelecimento, espaço e intervalo.
2. T1, T2 e T3 são registros independentes em `booking_timers`, com prazo, início, fim e status próprios. Nenhum temporizador reinicia quando outro termina.
3. T1 começa na criação da reserva; ao confirmar todas as vagas, a reserva passa a `REQUESTED` e T2 começa.
4. T2 usa **tempo corrido** na 13A. Horário comercial, dias fechados e prazo máximo separado ficam pendentes; a configuração `JOGA_BOOKING_T2_MAX_MINUTES` já existe.
5. O aceite do estabelecimento cria um `booking_holds` ativo e passa por `HOLD_CONFIRMED` para `PAYMENT_PENDING`, abrindo uma cobrança simulada por vaga.
6. T3 tem prazo total configurável e um buffer operacional. O pagamento termina antes do fim do hold; não há prorrogação automática.
7. A confirmação exige que todas as vagas ativas estejam pagas. Pagamento é simulado apenas em ambiente local/teste; PSP real é Fase 14.
8. A substituição preserva a vaga, a contribuição e o prazo de T3. O participante substituído com pagamento pago é marcado para reembolso simulado; o novo participante recebe nova cobrança na mesma vaga.
9. O hold é transacional. O aceite trava a linha do espaço e verifica holds e reservas bloqueantes antes de criar novo hold.
10. O backend é a autoridade dos prazos. Worker `advance_bookings` expira timers vencidos e libera holds; endpoints também rejeitam operação após o prazo mesmo com worker atrasado.
11. Toda transição grava `booking_events` com ator, estado anterior, novo estado, motivo e timestamp, além da auditoria da organização.
12. A conclusão da reserva (`COMPLETED`) é operacional, feita pelo estabelecimento, até existir integração com o ciclo da partida.

## Alternativas consideradas

### A. Usar apenas timestamps na reserva

Mais simples, mas dificulta auditar independência, expiração e idempotência. A tabela de timers foi adotada.

### B. Deixar o cliente controlar prazos

Rejeitada: relógio, notificação e conexão não são fonte oficial.

### C. Implementar T2 em horário comercial desde já

Exige calendário de funcionamento, feriados e exceções. Fica pendente para não bloquear a 13A.

### D. Simular pagamento como se fosse PSP

Aceito apenas em local/teste e explicitamente separado do fluxo real.

## Consequências

- A 13A fecha o ciclo de reserva e bloqueio sem cobrança real.
- O horário comercial de T2 e a política definitiva de reembolso permanecem pendentes.
- O painel cobre aceite, recusa, conclusão e acompanhamento; o mobile ainda não tem a jornada completa.
- A Fase 14 deve substituir o pagamento simulado por PSP, webhooks e reembolso real, mantendo a máquina de estados.
- A conclusão automática pelo ciclo da partida ainda não está ligada.

## Critérios para revisão

- Definição do calendário de funcionamento para T2.
- Contrato de PSP e política de reembolso.
- Integração com o ciclo da partida para conclusão automática.
- Evidência de abuso, fraude ou disputa que exija novas regras.
