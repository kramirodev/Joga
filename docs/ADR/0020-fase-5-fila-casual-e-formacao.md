# ADR 0020 — Fase 5: fila casual, formação transacional e política de balanceamento

- **Status:** Aprovado pelo responsável do produto em 2026-11-03, ao autorizar o início da Fase 5.
- **Data:** 2026-11-03
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** `PLANS.md` (Fase 5), `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` §7 e §8, `docs/JOGA_DOCUMENTACAO_TECNICA.md` §8, ADR 0019.

## Contexto

A Fase 4 entregou perfil, disponibilidade semanal, região por CEP/GPS e descoberta de locais. A Fase 5 precisa transformar entradas de fila em partidas, com persistência no PostgreSQL, formação transacional e worker recuperável.

O MMR é escopo da Fase 8. Formar partidas usando um rating inexistente produziria um contrato que precisaria ser refeito, e partidas casuais não alteram MMR de qualquer forma.

## Decisão

1. **Somente casual nesta fase.** A coluna `mode` existe e aceita `casual` e `ranked`, mas a API rejeita `ranked` com `400 ranked_not_available` até a Fase 8. Assim o contrato não muda quando o ranqueado chegar.
2. **Janela de horário vem da agenda do perfil.** Quem entra na fila usa as janelas semanais da Fase 4. O worker procura o primeiro horário livre nos próximos **7 dias**, em slots de **30 minutos**, com antecedência mínima de **2 horas** e duração copiada do formato.
3. **Balanceamento `level_v1`.** As equipes são divididas pelo nível autodeclarado (`beginner` = 1, `intermediate` = 2, `advanced` = 3), minimizando a diferença de soma entre os dois lados. A versão da política é gravada no lobby e no registro da execução.
4. **MMR fica para a Fase 8 como `mmr_v1`.** Quando existir, o balanceamento parte da nota base e separa quem ainda não jogou ranqueada. A política é escolhida por versão registrada, sem alterar o schema da fila.
5. **Região de encontro calculada pelo servidor.** O centro do lobby é a média geográfica dos centros aproximados das entradas e o raio é o menor raio informado, limitado a 30 km. Nenhuma coordenada exata é usada ou exposta.
6. **Preferência de quadra por interseção.** `PUBLIC_ONLY` + `PRIVATE_ONLY` é incompatível; `ANY` é neutro. A preferência efetiva fica gravada no lobby.
7. **Sem local nesta fase.** O catálogo de `venues` continua vazio por decisão da Fase 4; o lobby guarda a região de encontro e `venue_id` nasce nulo. Escolha de quadra é Fase 9/14.
8. **Worker separado e idempotente.** Processo próprio consome entradas com `SELECT ... FOR UPDATE SKIP LOCKED`, revalida dentro da transação e grava `lobbies`, `lobby_participants` e o registro da execução. `scripts/run_matchmaking.py` executa uma rodada ou em loop; a API não forma partidas.
9. **Entrada expira.** A entrada vale por 24 horas ou até o usuário sair/entrar numa partida; expiração é marcada pelo worker na rodada seguinte.

## Consequências

- A Fase 5 não depende de MMR e não cria tabela de rating.
- Quando a Fase 8 chegar, basta adicionar a política `mmr_v1` e permitir `ranked` na API; fila, lobby e participantes permanecem.
- Lobbies nascem `scheduled`, com data/hora concreta; a máquina de estados da Fase 6 evolui a partir daí.
- Como o catálogo de locais está vazio, a descoberta continua retornando zero; o lobby existe com região, sem quadra definida.
- A formação é limitada a grupos do mesmo formato e modo; misturar formatos exigiria nova decisão.
