# ADR 0041 — Trust Factor: eventos, recuperação e restrição ranqueada

- **Status:** Aprovado e implementado em 2026-11-09.
- **Data:** 2026-11-09
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** ADR 0025 (Trust Factor), ADR 0039 (cancelamento/substituição/presença), `docs/JOGA_DOCUMENTACAO_TECNICA.md` §11.2/§14.

## Contexto

Era necessário transformar o Trust Factor em uma métrica interna acionável: penalizar quem prejudica a experiência dos outros, recuperar quem joga normalmente e restringir apenas partidas ranqueadas quando necessário. O score não deve ser exibido ao jogador; a restrição é o efeito palpável.

## Decisão

1. O Trust Factor começa em **100** e é uma métrica **interna e oculta**.
2. Eventos negativos:
   - `no_show`: **−30** (severidade 5).
   - `cancel_after_confirmation`: **−7** (severidade 3).
   - `cancel_before_payment`: **−2** (severidade 1).
3. Recuperação ao concluir partida (`match_completed`), não linear e com teto:
   ```text
   recuperação = min(6, max(1, ceil((100 − score) · 0,2)))
   ```
   Quanto mais baixo o score, maior a recuperação; perto de 100, ela desacelera e nunca passa de 100.
4. Reincidência dentro de 30 dias:
   ```text
   multiplicador = min(2,0, 1 + 0,5 · eventos_negativos_nos_últimos_30_dias)
   penalidade = ceil(base · multiplicador)
   ```
   Exemplos: 1º no-show −30; 2º −45; 3º −60. Cancelamento após confirmação: −7, −11, −14.
5. Restrição ranqueada:
   - **2 no-shows** ou **3 cancelamentos após confirmação** em 30 dias → **7 dias** sem fila ranqueada;
   - **3 no-shows** ou **4 cancelamentos após confirmação** em 30 dias → **30 dias**;
   - a maior restrição existente prevalece; casual continua permitido;
   - o suporte (responsável pelo produto) pode revisar/retirar a restrição com justificativa e auditoria.
6. Nenhum endpoint público expõe score, eventos ou histórico. O jogador percebe apenas a impossibilidade temporária de entrar na fila ranqueada.
7. Eventos são append-only; correções são novos eventos, não exclusões.
8. A restrição é aplicada no `enqueue` da fila ranqueada; a fila casual não é bloqueada.

## Consequências

- `trust_accounts.ranked_restricted_until` armazena a restrição.
- `TrustService.apply_event` atualiza score, registra evento e aplica a restrição.
- Hooks: desistência após confirmação, no-show, cancelamento antes do pagamento e partida concluída.
- `bookings.presence_status` é a fonte para a recuperação por partida concluída.
- O score não aparece no painel/mobile; a UI de suporte e a contestação formal ficam pendentes.
- Os pesos são iniciais e podem ser recalibrados com dados do piloto, mantendo versionamento.

## Pendências

- UI de suporte para revisar/retirar restrições.
- Notificação ao jogador de que está temporariamente restrito (sem revelar score).
- Contestação/recuperação por emergência e força maior.
- Calibração com dados reais de no-show, cancelamento e retenção.
