# Fase 17B — Moderação operacional e limites de abuso

**Status:** implementado no backend em 2026-11-14.
**Depende de:** 17A (denúncias), Fase 9 (notificações), Fase 6 (partidas).
**Não inclui:** painel web interno, classificador de IA treinado, suspensão permanente automática ou retenção definitiva.

## Problema

A 17A já denunciava e priorizava, mas não tinha:

- consequência para denúncia falsa;
- suspensão temporária aplicada por operador;
- reativação automática;
- rotina de retenção/redação do contexto;
- caminho definido para IA local.

## Decisões

1. **Sem IA paga.** A triagem continua determinística (`rules_v1`). O
   classificador local/open-source só entra depois de dataset rotulado e
   avaliação offline; a interface já é substituível.
2. **Denúncia falsa:** 3 denúncias improcedentes em 30 dias geram cooldown de
   7 dias para abrir novas denúncias. É reversível e não altera Trust Factor.
3. **Suspensão temporária:** medida `SUSPEND_TEMP`, de 1 a 30 dias, aplicada
   apenas por operador humano. A conta fica `suspended` e não autentica.
4. **Suspensão permanente** permanece fora desta fatia; exige política,
   revisão jurídica e segundo revisor.
5. **Reativação:** `scripts/reactivate_suspensions.py` devolve a conta a
   `active` ao fim do prazo.
6. **Retenção provisória:** após 180 dias, descrição e contexto são redigidos;
   categoria, status, prioridade, decisão e auditoria permanecem.
7. **Painel interno** continua CLI nesta fatia; a interface web separada fica
   para a 17C.

## Superfície

- `SUSPEND_TEMP` em `POST /moderation/actions/...` via CLI.
- Recurso aceita revogar a suspensão.
- Nenhum endpoint interno de fila é público.

## Operação

```powershell
# decisão
python -m scripts.review_moderation --decide <id> \
  --decision SUSPEND_TEMP --days 3 \
  --reason "Ameaça grave" --operator op1

# reativação de vencidas
python -m scripts.reactivate_suspensions

# retenção/redação
python -m scripts.cleanup_moderation --dry-run
python -m scripts.cleanup_moderation
```

Variáveis:

```text
JOGA_MODERATION_FALSE_REPORT_THRESHOLD=3
JOGA_MODERATION_FALSE_REPORT_COOLDOWN_DAYS=7
JOGA_MODERATION_RETENTION_DAYS=180
```

## Modelo

Migração `a3b4c5d6e7f8`:

- `users.suspended_until`;
- `moderation_actions.action_type` aceita `SUSPEND_TEMP`.

## Testes

- `tests/test_moderation.py`: suspensão bloqueia autenticação, revogação
  restaura, cooldown de denúncia falsa e limites de contexto.
- Suíte completa: **469 passed, 29 skipped**.
- Migração: upgrade, downgrade e novo upgrade.

## Pendente

1. Painel web interno separado do JOGA y GESTÃO.
2. Classificador local/open-source com dataset e avaliação offline.
3. Suspensão permanente com dupla revisão e política jurídica.
4. Retenção definitiva/LGPD e direito de exclusão.
5. Consequência para denúncia coordenada.
6. Integração de UI no app.
