# Fase 17A — Denúncias e moderação humana mínima

**Status:** implementado no backend em 2026-11-14.
**Depende de:** Fase 9 (chat/lobby), Fase 16 (clãs) e configuração de operadores.
**Não inclui:** IA generativa, classificação automática de texto, painel web de moderação, consequência para denúncia falsa ou retenção definitiva.

## Decisão sobre IA

A 17A **não usa IA paga**. A triagem é determinística (`rules_v1`) e serve
apenas para priorizar a fila humana. O texto não é enviado a terceiros.

Motivos:

- custo recorrente zero;
- nenhum envio de conteúdo sensível para provedor externo;
- ausência de dataset rotulado para treinar/validar um classificador;
- a decisão continua humana e auditável;
- a interface `ModerationClassifier` permite trocar por um modelo
  local/open-source depois, sem alterar o domínio.

Quando houver dados e orçamento, a evolução recomendada é um classificador
local/open-source em português, avaliado offline, e nunca um fornecedor pago
como dependência do fluxo crítico.

## Fluxo

1. Jogador denuncia outro participante do mesmo lobby.
2. Pode anexar até 5 mensagens do alvo no lobby.
3. O backend valida vínculo, autoria, tamanho e limites.
4. A triagem calcula prioridade/severidade por categoria, reincidência e
   contexto.
5. A denúncia fica `OPEN` para revisão humana.
6. Operador decide `DISMISS`, `WARN` ou `RESTRICT_RANKED`.
7. Medida gera notificação e auditoria.
8. O alvo pode recorrer; outro operador decide o recurso.
9. Recurso aceito revoga a medida.

## Superfície do jogador

| Método | Rota | Efeito |
|---|---|---|
| POST | `/api/v1/moderation/reports` | Cria denúncia com contexto |
| GET | `/api/v1/moderation/reports/me` | Histórico do denunciante |
| GET | `/api/v1/moderation/actions/me` | Medidas recebidas |
| POST | `/api/v1/moderation/actions/{action_id}/appeal` | Abre recurso |

## Revisão interna

CLI:

```powershell
python -m scripts.review_moderation --list
python -m scripts.review_moderation --decide <id> --decision WARN \
  --reason "Aviso formal" --operator op1
python -m scripts.review_moderation --decide <id> --decision RESTRICT_RANKED \
  --days 7 --reason "Restrição ranqueada" --operator op1
python -m scripts.review_moderation --appeals
```

Operadores vêm de `JOGA_MODERATION_OPERATORS` (nomes separados por vírgula).
Lista vazia significa nenhum operador autorizado.

## Modelo

Migração `f2a3b4c5d6e7`:

- `moderation_reports`: denunciante, alvo, lobby, categoria, descrição,
  contexto, status, prioridade, severidade, classificação e revisão;
- `moderation_actions`: aviso ou restrição ranqueada reversível;
- `moderation_appeals`: recurso com decisão humana separada.

## Limites

- Denúncia isolada não gera punição automática.
- A IA não decide medida.
- `RESTRICT_RANKED` afeta apenas a fila ranqueada; não suspende a conta.
- Não há upload de mídia.
- O contexto é textual, privado e limitado a mensagens do alvo no lobby.
- A ferramenta interna é CLI nesta fatia; o painel separado fica pendente.

## Testes

`tests/test_moderation.py`: triagem, contexto, limite de frequência, isolamento,
aviso com notificação, restrição reversível por recurso e autorização.

## Pendente

1. Painel interno de moderação separado do painel de gestão.
2. Classificador local/open-source, após dataset e avaliação offline.
3. Consequência para denúncia falsa e limites por jogador.
4. Retenção/LGPD de descrição, contexto e evidências.
5. Revisão humana de mídia (fora do MVP).
6. Integração de UI no app.
