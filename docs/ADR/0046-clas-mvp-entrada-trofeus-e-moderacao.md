# ADR 0046 — Clãs no MVP: entrada, troféus e moderação mínima

- **Status:** Aprovado e implementado no backend em 2026-11-13.
- **Data:** 2026-11-13
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** ADR 0025 (MMR e troféus), ADR 0043 (temporada), ADR 0044 (clãs no MVP).

## Contexto

A ADR 0044 antecipou clãs para o MVP e deixou quatro decisões abertas: tamanho,
regra de entrada, troca e temporada de troféus. A PENDENCIAS também apontava a
fórmula 50/30/20 e o corte mínimo de moderação como bloqueios. Sem esses números,
nem o schema nem o contrato do chat podiam ser fechados.

## Decisão

1. **Tamanho máximo de 30 membros por clã.**
2. **Entrada por aprovação** é a política padrão. O clã pode optar por `open`
   (entra direto) ou `closed` (não aceita pedidos). A aprovação é sempre humana,
   feita por dono ou admin.
3. **Um clã ativo por jogador**, garantido por índice único parcial no banco.
4. **Troca de clã é livre, com carência de 7 dias** depois de sair ou ser
   removido. A carência é por jogador, não por clã.
5. **Dono não sai sem transferir.** A transferência promove o novo dono e rebaixa
   o anterior a admin.
6. **Papéis:** dono, admin e membro. Dono promove/rebaixa e remove qualquer um;
   admin remove apenas membros comuns.
7. **Troféus são por temporada e formato.** Cada partida finalizada rende, por
   jogador presente no clã: **vitória 50, empate 30, derrota 20** — a leitura
   literal da fórmula 50/30/20. Só conta quem tem **7 dias de permanência** no
   clã na data da partida, e a soma usa os **10 melhores membros** do clã na
   temporada/formato. É evento append-only, idempotente por
   `(match_id, user_id)`.
8. **Troféu é do clã e não se compra, transfere nem recebe por publicidade.**
   Trocar de clã não leva os troféus. A temporada encerra com **snapshot
   auditável** por clã e formato.
9. **Chat do clã** é separado do chat do lobby, só para membros ativos, com
   corpo de 1 a 2000 caracteres.
10. **Denúncia oculta a mensagem imediatamente.** A mensagem não é apagada:
    ganha `hidden_at`, e o admin decide entre manter oculta ou restaurar. A
    decisão fica registrada com autor e data.
11. **Moderação mínima acompanha a Fase 16:** denúncia, ocultação imediata,
    fila de revisão do clã e registro auditável.

## Consequências

- O schema ganha `clans`, `clan_members`, `clan_join_requests`,
  `clan_trophy_events`, `clan_messages` e `clan_reports` (migração
  `b7d4f1a9c620`).
- O ranking de clãs é por temporada e formato, sem expor MMR.
- O chat de clã tem custo de moderação desde o primeiro dia; não existe chat
  aberto sem denúncia.
- A carência de 7 dias reduz o "turismo de clã" sem impedir a troca.
- Nada disso altera matchmaking, MMR, Trust Factor ou o resultado da partida.

## Riscos

1. **Fórmula 50/30/20 sem dados.** A leitura vitória/empate/derrota é simples e
   auditável, mas pode inflar clãs com muito volume. Calibrar no piloto.
2. **Clã de 30 membros** pode esvaziar a descoberta em cidades pequenas. Medir
   ocupação e permitir mais de um clã por jogador no futuro, se necessário.
3. **Denúncia usada como arma.** Ocultação imediata é reversível e auditada, mas
   denúncias falsas precisam de consequência; fica para a Fase 17.
4. **Uma temporada de troféus por trimestre** pode ficar longa demais; a ADR
   0044 já previa revisão.

## Pendências

1. Calibrar a fórmula de troféus com dados reais.
2. Definir consequência para denúncia falsa e limite de denúncias por jogador.
3. Definir se o clã pode ter escudo e cores próprias no MVP.
4. Definir o que acontece com o clã quando o dono exclui a conta.
5. Definir evento de Marketing e data-alvo da Fase 16.
